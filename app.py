"""Guild Master RPG: web local y Railway.  Usa exclusivamente el esquema del grupo."""
from __future__ import annotations
import io
import os
import secrets
import sqlite3
import tempfile
import re
from datetime import timedelta
from pathlib import Path
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from database import initialize, connect, shared_db_path
from game import GameError, assign, buy, payroll, recover, recruit, resolve, state, toggle_equip
from forest_bridge import forest_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_NAME'] = 'guild_master_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = bool(os.environ.get('RAILWAY_ENVIRONMENT'))
app.config['MAX_CONTENT_LENGTH'] = 16_384
app.permanent_session_lifetime = timedelta(days=365)

# Sin contraseña: cada navegador recibe un identificador aleatorio firmado
# en la cookie de sesión de Flask. La base de cada partida permanece en /data/players.
# La base compartida de la versión anterior se conserva sin exponerla a visitantes.
initialize(shared_db_path())
app.register_blueprint(forest_bp)

@app.before_request
def guard():
    if request.path == '/health' or request.path.startswith('/static/'):
        return
    player_id = session.get('guild_player_id')
    if not isinstance(player_id, str) or not re.fullmatch(r'[0-9a-f]{32}', player_id):
        session.clear()
        session['guild_player_id'] = secrets.token_hex(16)
    session.permanent = True
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(30)
    if request.method == 'POST':
        token = request.form.get('csrf') or request.headers.get('X-CSRF-Token', '')
        if not secrets.compare_digest(token, session['csrf']):
            abort(400, 'Formulario inválido. Actualizá la página y volvé a intentar.')

@app.get('/health')
def health():
    try:
        with connect(path=shared_db_path()) as db:
            db.execute('SELECT COUNT(*) FROM Aventurero').fetchone()
        return {'status':'ok'}, 200
    except (sqlite3.Error, RuntimeError):
        return {'status':'error'}, 503

@app.context_processor
def globals_for_templates():
    return {'csrf': session.get('csrf', ''), 'auth_enabled': False}

@app.get('/')
def inicio():
    return render_template('home.html',g=state(), section='inicio')

@app.get('/aventureros')
def aventureros():
    return render_template('heroes.html',g=state(), section='heroes')

@app.get('/misiones')
def misiones():
    return render_template('missions.html',g=state(), section='missions')

@app.get('/armeria')
def armeria():
    return render_template('armory.html',g=state(), section='armory')

@app.get('/tesoro')
def tesoro():
    return render_template('treasury.html',g=state(), section='treasury')

ACTIONS = {
    'reclutar': (lambda f: recruit(f.get('nombre'),f.get('clase')),'aventureros'),
    'asignar': (lambda f: assign(f.get('mision_id'),f.getlist('heroe_id')),'misiones'),
    'comprar': (lambda f: buy(f.get('heroe_id'),f.get('item_id')),'armeria'),
    'equipar': (lambda f: toggle_equip(f.get('heroe_id'),f.get('item_id')),'armeria'),
    'pagar': (lambda f: payroll(),'tesoro'),
    'recuperar': (lambda f: recover(f.get('heroe_id')),'aventureros'),
}

@app.post('/accion/<accion>')
def accion(accion):
    if accion not in ACTIONS: abort(404)
    operation, back = ACTIONS[accion]
    try:
        msg=operation(request.form)
    except (GameError, sqlite3.IntegrityError, ValueError) as exc:
        flash(str(exc), 'error')
    except sqlite3.OperationalError:
        app.logger.exception('Error SQL')
        flash('No se pudo completar la operación. Revisá la conexión a SQLite.', 'error')
    else:
        flash(msg,'success')
    return redirect(url_for(back))


# La micromazmorra V2 queda sustituida: solo Dark Forest puede cerrar misiones.

@app.get('/respaldo')
def respaldo():
    """Copia consistente de SQLite, no se lee el archivo a mitad de una transacción."""
    with tempfile.TemporaryDirectory() as folder:
        dest=Path(folder)/'partida.db'
        with connect() as source:
            target=sqlite3.connect(str(dest))
            try:
                source.backup(target)
            finally:
                target.close()
        payload=dest.read_bytes()
    return send_file(io.BytesIO(payload), mimetype='application/vnd.sqlite3',
                     as_attachment=True,download_name='guild_master_partida.db')

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=False)
