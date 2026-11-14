"""Base de datos del gremio: no altera el esquema SQL entregado por el equipo."""
from __future__ import annotations
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from flask import has_request_context, session

ROOT = Path(__file__).resolve().parent
SQL_PATH = ROOT / 'gremioDDLg6.sql'
_INITIALIZE_LOCK = threading.Lock()


def shared_db_path() -> Path:
    """Partida heredada de V3.3: se preserva, no se asigna a visitantes."""
    return Path(os.environ.get('DB_PATH') or ROOT / 'data' / 'gremio.db').expanduser().resolve()


def db_path() -> Path:
    base = shared_db_path()
    if not has_request_context():
        return base
    player_id = session.get('guild_player_id')
    if not isinstance(player_id, str) or not re.fullmatch(r'[0-9a-f]{32}', player_id):
        raise RuntimeError('No se pudo identificar esta partida.')
    return base.parent / 'players' / (player_id + '.db')


def _new_connection(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(path), timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    c.execute('PRAGMA busy_timeout = 15000')
    return c


def initialize(path: Path | None = None) -> Path:
    """Inicialización única, protegida frente a dos peticiones del mismo visitante."""
    with _INITIALIZE_LOCK:
        return _initialize_locked(path)


def _initialize_locked(path: Path | None = None) -> Path:
    """No reinicializar ni sobrescribir una partida existente."""
    path = Path(path or db_path()).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        db=_new_connection(path)
        try:
            if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Aventurero'").fetchone():
                raise RuntimeError(f'La base existente no tiene el esquema esperado: {path}')
        finally:
            db.close()
        return path
    if not SQL_PATH.exists():
        raise RuntimeError(f'Falta {SQL_PATH.name}. Colocalo en la raiz del repositorio.')
    # Construimos primero en un fichero temporal para no dejar una BD incompleta tras un error.
    temp = path.with_name(path.name + '.inicializando')
    if temp.exists():
        temp.unlink()
    try:
        db = _new_connection(temp)
        try:
            db.executescript(SQL_PATH.read_text(encoding='utf-8-sig'))
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Fallo de integridad al crear la BD')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Claves foraneas invalidas en los datos iniciales')
            if db.in_transaction:
                raise RuntimeError('El SQL final deja una transaccion abierta')
        finally:
            db.close()
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return path


@contextmanager
def connect(path: Path | None = None):
    db=_new_connection(initialize(path))
    try:
        yield db
        if db.in_transaction:
            db.rollback()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()
