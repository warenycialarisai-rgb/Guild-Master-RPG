"""Puente Dark Forest (Phaser) ↔ Guild Master (SQLite): no altera el esquema.

La partida web original informa de victoria o derrota; el servidor controla que
la misión y la cuadrilla existan, que el intento pertenezca a la sesión y que
una misión no pueda resolverse ni pagarse dos veces. No es un anti-cheat:
el resultado gráfico, como en cualquier juego cliente, podría falsificarse.
"""
from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from database import connect
from game import GameError, resolve, state

forest_bp = Blueprint('dark_forest', __name__)
ASSET_ROOT = Path(__file__).resolve().parent / 'static' / 'darkforest'
RUN_MAX_SECONDS = 2 * 60 * 60
RUN_MIN_SECONDS = 8


def _installed() -> bool:
    return ((ASSET_ROOT / 'project.bundle.js').is_file() and
            (ASSET_ROOT / 'assets' / 'images' / 'map' / 'dark_forest.json').is_file())


def _squad(db, mission_id):
    """Los miembros y bonificaciones se obtienen de las tablas oficiales."""
    rows = db.execute('''
        SELECT a.id, a.nombre, a.clase, a.nivel,
               COALESCE(SUM(CASE WHEN ia.equipado=1 THEN e.bonus_ataque*ia.cantidad ELSE 0 END), 0) AS ataque,
               COALESCE(SUM(CASE WHEN ia.equipado=1 THEN e.bonus_defensa*ia.cantidad ELSE 0 END), 0) AS defensa
        FROM Asignacion_Mision am
        JOIN Aventurero a ON a.id=am.id_aventurero
        LEFT JOIN Inventario_Aventurero ia ON ia.id_aventurero=a.id
        LEFT JOIN Equipamiento e ON e.id=ia.id_equipamiento
        WHERE am.id_mision=? AND am.resultado IS NULL AND a.estado='en_mision'
        GROUP BY a.id ORDER BY a.id
    ''', (mission_id,)).fetchall()
    return [dict(row) for row in rows]


@forest_bp.get('/bosque/<int:mission_id>')
def bosque(mission_id):
    """Abre una partida de Dark Forest solo para misiones realmente activas."""
    with connect() as db:
        mission = db.execute('SELECT id,titulo,estado,nivel_dificultad FROM Mision WHERE id=?',
                             (mission_id,)).fetchone()
        squad = _squad(db, mission_id) if mission else []
    if not mission or mission['estado'] != 'en_progreso' or not squad:
        flash('Para entrar al bosque, primero debés tener una misión en progreso con una cuadrilla asignada.', 'error')
        return redirect(url_for('misiones'))

    token = secrets.token_urlsafe(32)
    runs = dict(session.get('dark_forest_runs', {}))
    runs[str(mission_id)] = dict(token=token, started=time.time(),
                                 squad_ids=[int(hero['id']) for hero in squad])
    session['dark_forest_runs'] = runs
    installed = _installed()
    return render_template('forest.html', g=state(), section='missions',
                           mission=dict(mission), squad=squad, token=token,
                           installed=installed)


@forest_bp.post('/bosque/<int:mission_id>/resultado')
def resultado(mission_id):
    """Cierra y registra una misión en una única transacción ya implementada en game.py."""
    if not request.is_json:
        return jsonify(ok=False,error='Se requiere JSON.'), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload,dict) or type(payload.get('victory')) is not bool:
        return jsonify(ok=False,error='Resultado inválido.'), 400
    if not _installed():
        return jsonify(ok=False,error='La instalación de Dark Forest está incompleta.'), 409
    runs = dict(session.get('dark_forest_runs', {}))
    attempt = runs.get(str(mission_id))
    token = payload.get('token')
    if not attempt or not isinstance(token,str) or not secrets.compare_digest(token,attempt['token']):
        return jsonify(ok=False,error='Intento inexistente o no autorizado.'), 409
    elapsed = time.time() - attempt['started']
    if elapsed < RUN_MIN_SECONDS or elapsed > RUN_MAX_SECONDS:
        return jsonify(ok=False,error='Duración de la expedición inválida o caducada.'), 409

    try:
        with connect() as db:
            mission = db.execute('SELECT estado FROM Mision WHERE id=?', (mission_id,)).fetchone()
            squad = _squad(db, mission_id)
            if (not mission or mission['estado'] != 'en_progreso' or
                [int(h['id']) for h in squad] != attempt['squad_ids']):
                raise GameError('La misión o la cuadrilla cambiaron durante la expedición.')
        message = resolve(mission_id, expedition_outcome=payload['victory'])
    except (GameError, sqlite3.Error) as exc:
        return jsonify(ok=False,error=str(exc)), 409

    runs.pop(str(mission_id),None)
    session['dark_forest_runs'] = runs
    flash(message, 'success' if payload['victory'] else 'error')
    return jsonify(ok=True, message=message, redirect=url_for('misiones'))
