"""Reglas mínimas de Guild Master RPG; SQL parametrizado y transacciones atómicas."""
from __future__ import annotations
import sqlite3
from database import connect

class GameError(Exception):
    pass

SALARIOS = {'guerrero': 100, 'mago': 120, 'arquero': 90}
OBJETIVO_MISIONES = 5


def _balance(db):
    return float(db.execute('SELECT saldo_actual FROM vista_resumen_gremio').fetchone()[0])


def state():
    with connect() as db:
        resumen = dict(db.execute('SELECT * FROM vista_resumen_gremio').fetchone())
        heroes = [dict(x) for x in db.execute('''
            SELECT a.*, COALESCE(SUM(CASE WHEN ia.equipado = 1 THEN e.bonus_ataque*ia.cantidad ELSE 0 END),0) AS ataque,
                   COALESCE(SUM(CASE WHEN ia.equipado = 1 THEN e.bonus_defensa*ia.cantidad ELSE 0 END),0) AS defensa
            FROM Aventurero a
            LEFT JOIN Inventario_Aventurero ia ON a.id=ia.id_aventurero
            LEFT JOIN Equipamiento e ON e.id=ia.id_equipamiento
            GROUP BY a.id ORDER BY a.id
        ''')]
        missions = [dict(x) for x in db.execute('''
            SELECT m.*, COALESCE(GROUP_CONCAT(a.nombre, ', '), '') AS equipo
            FROM Mision m LEFT JOIN Asignacion_Mision am ON am.id_mision=m.id
            LEFT JOIN Aventurero a ON a.id=am.id_aventurero
            GROUP BY m.id ORDER BY CASE m.estado WHEN 'en_progreso' THEN 0 WHEN 'pendiente' THEN 1 ELSE 2 END, m.id
        ''')]
        items = [dict(x) for x in db.execute('SELECT * FROM Equipamiento ORDER BY tipo, costo_oro, id')]
        inventory = [dict(x) for x in db.execute('''
            SELECT ia.*, a.nombre AS heroe, e.nombre AS objeto, e.tipo, e.bonus_ataque, e.bonus_defensa
            FROM Inventario_Aventurero ia JOIN Aventurero a ON a.id=ia.id_aventurero
            JOIN Equipamiento e ON e.id=ia.id_equipamiento
            ORDER BY a.id, e.tipo
        ''')]
        history = [dict(x) for x in db.execute('SELECT * FROM Tesoro ORDER BY id DESC LIMIT 12')]
        completed = sum(m['estado']=='completada' for m in missions)
        active = sum(m['estado']=='en_progreso' for m in missions)
        pending = sum(m['estado']=='pendiente' for m in missions)
        result = 'victoria' if completed >= OBJETIVO_MISIONES else ('derrota' if active+pending==0 else None)
        return dict(resumen=resumen, heroes=heroes, missions=missions, items=items,
                    inventory=inventory, history=history, completed=completed,
                    active=active, pending=pending, goal=OBJETIVO_MISIONES, result=result)


def _playing(db):
    n = db.execute("SELECT COUNT(*) FROM Mision WHERE estado='completada'").fetchone()[0]
    open_m = db.execute("SELECT COUNT(*) FROM Mision WHERE estado IN ('pendiente','en_progreso')").fetchone()[0]
    if n >= OBJETIVO_MISIONES or open_m == 0:
        raise GameError('La temporada terminó. Iniciá una nueva partida para seguir jugando.')


def recruit(name, char_class):
    name = (name or '').strip()
    if not 2 <= len(name) <= 32 or any(ord(x)<32 for x in name):
        raise GameError('El nombre debe tener entre 2 y 32 caracteres válidos.')
    if char_class not in SALARIOS:
        raise GameError('Clase no admitida.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        if db.execute('SELECT id FROM Aventurero WHERE nombre=? COLLATE NOCASE',(name,)).fetchone():
            raise GameError('Ya existe un aventurero con ese nombre.')
        db.execute('''INSERT INTO Aventurero(nombre,clase,nivel,salario_diario,estado,experiencia)
                      VALUES(?,?,1,?,'disponible',0)''',(name,char_class,SALARIOS[char_class]))
        db.commit()
    return f'{name} se unió al gremio.'


def assign(mission_id, hero_ids):
    try:
        mission_id = int(mission_id)
        hero_ids = [int(x) for x in hero_ids]
    except (TypeError,ValueError):
        raise GameError('Selección inválida.')
    if not 1<=len(hero_ids)<=3 or len(set(hero_ids))!=len(hero_ids):
        raise GameError('Elegí entre 1 y 3 aventureros distintos.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        updated = db.execute("UPDATE Mision SET estado='en_progreso' WHERE id=? AND estado='pendiente'",(mission_id,))
        if updated.rowcount != 1:
            raise GameError('La misión no está disponible.')
        for h in hero_ids:
            u=db.execute("UPDATE Aventurero SET estado='en_mision' WHERE id=? AND estado='disponible'",(h,))
            if u.rowcount!=1:
                raise GameError('Uno de los aventureros no está disponible.')
            db.execute('INSERT INTO Asignacion_Mision(id_aventurero,id_mision,resultado,xp_ganada) VALUES(?,?,NULL,0)',(h,mission_id))
        db.commit()
    return f'Cuadrilla de {len(hero_ids)} aventurero(s) enviada.'


def resolve(mission_id, expedition_outcome: bool | None = None):
    try: mission_id=int(mission_id)
    except (TypeError,ValueError): raise GameError('Misión inválida.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        m=db.execute("SELECT * FROM Mision WHERE id=? AND estado='en_progreso'",(mission_id,)).fetchone()
        if not m: raise GameError('La misión no puede resolverse.')
        squad=db.execute('''
            SELECT a.id,a.nombre,a.nivel,
                   COALESCE(SUM(CASE WHEN ia.equipado=1 THEN e.bonus_ataque*ia.cantidad + e.bonus_defensa*ia.cantidad ELSE 0 END),0) AS bonificacion
            FROM Asignacion_Mision am JOIN Aventurero a ON a.id=am.id_aventurero
            LEFT JOIN Inventario_Aventurero ia ON ia.id_aventurero=a.id
            LEFT JOIN Equipamiento e ON e.id=ia.id_equipamiento
            WHERE am.id_mision=? AND am.resultado IS NULL GROUP BY a.id
        ''',(mission_id,)).fetchall()
        if not squad: raise GameError('La misión no tiene cuadrilla activa.')
        # Regla determinista, transparente y reproducible para la defensa oral.
        power=sum(h['nivel'] + int(h['bonificacion'])//12 for h in squad)
        # Sin expedición, conserva la lógica V1; el resultado interactivo lo decide el servidor.
        if expedition_outcome is not None and not isinstance(expedition_outcome, bool):
            raise GameError('Resultado de expedición inválido.')
        success=(power>=int(m['nivel_dificultad'])
                 if expedition_outcome is None else expedition_outcome)
        next_status='completada' if success else 'fallida'
        if db.execute("UPDATE Mision SET estado=? WHERE id=? AND estado='en_progreso'",(next_status,mission_id)).rowcount!=1:
            raise GameError('La misión ya fue resuelta.')
        for h in squad:
            xp=int(m['nivel_dificultad'])*75 if success else 0
            db.execute('UPDATE Asignacion_Mision SET resultado=?,xp_ganada=? WHERE id_aventurero=? AND id_mision=?',
                       ('exitoso' if success else 'herido',xp,h['id'],mission_id))
            if success:
                hero=db.execute('SELECT nivel,experiencia FROM Aventurero WHERE id=?',(h['id'],)).fetchone()
                experience=hero['experiencia']+xp
                level=hero['nivel']
                while experience>=level*700:
                    level+=1
                db.execute("UPDATE Aventurero SET experiencia=?,nivel=?,estado='disponible' WHERE id=?",(experience,level,h['id']))
            else:
                db.execute("UPDATE Aventurero SET estado='herido' WHERE id=?",(h['id'],))
        if success:
            # La condicion de estado + la transaccion impide cobrar dos veces al resolver.
            db.execute("INSERT INTO Tesoro(tipo,monto,concepto,id_mision) VALUES('ingreso_mision',?,?,?)",
                       (m['recompensa_oro'],'Recompensa: '+m['titulo'],mission_id))
        db.commit()
    return (f"¡Victoria! Fuerza {power} contra dificultad {m['nivel_dificultad']}. "
            f"Ganaste {m['recompensa_oro']} oro y experiencia." if success else
            f"Derrota. Fuerza {power} contra dificultad {m['nivel_dificultad']}. Los héroes quedaron heridos.")


def buy(hero_id, item_id):
    try: hero_id,item_id=int(hero_id),int(item_id)
    except (TypeError,ValueError): raise GameError('Datos inválidos.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        hero=db.execute('SELECT nombre FROM Aventurero WHERE id=?',(hero_id,)).fetchone()
        if not hero: raise GameError('Aventurero inexistente.')
        item=db.execute('SELECT * FROM Equipamiento WHERE id=?',(item_id,)).fetchone()
        if not item: raise GameError('Objeto inexistente.')
        # La propia sentencia SQL comprueba la solvencia antes de registrar el egreso.
        paid=db.execute('''INSERT INTO Tesoro(tipo,monto,concepto,id_mision)
            SELECT 'egreso_equipo',costo_oro,?,NULL FROM Equipamiento
            WHERE id=? AND costo_oro <= (SELECT saldo_actual FROM vista_resumen_gremio)''',
            (f'Compra de {item["nombre"]} para {hero["nombre"]}',item_id))
        if paid.rowcount!=1: raise GameError('Oro insuficiente para comprar ese objeto.')
        db.execute('''INSERT INTO Inventario_Aventurero(id_aventurero,id_equipamiento,equipado,cantidad)
                      VALUES(?,?,0,1)
                      ON CONFLICT(id_aventurero,id_equipamiento)
                      DO UPDATE SET cantidad=cantidad+1''',(hero_id,item_id))
        db.commit()
    return f'{item["nombre"]} comprado para {hero["nombre"]}.'


def toggle_equip(hero_id,item_id):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        updated=db.execute('''UPDATE Inventario_Aventurero SET equipado=CASE equipado WHEN 1 THEN 0 ELSE 1 END
                              WHERE id_aventurero=? AND id_equipamiento=?''',(int(hero_id),int(item_id)))
        if updated.rowcount!=1: raise GameError('El objeto no está en el inventario.')
        db.commit()
    return 'Equipamiento actualizado.'


def payroll():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        rows=db.execute('SELECT COUNT(*) AS n, COALESCE(SUM(salario_diario),0) AS total FROM Aventurero').fetchone()
        total=float(rows['total'])
        if total<=0: raise GameError('No hay salarios que pagar.')
        paid=db.execute('''INSERT INTO Tesoro(tipo,monto,concepto,id_mision)
             SELECT 'egreso_salario',?, ?,NULL
             WHERE ? <= (SELECT saldo_actual FROM vista_resumen_gremio)''',
             (total,f'Pago de jornada a {rows["n"]} aventureros',total))
        if paid.rowcount!=1: raise GameError('No hay oro suficiente para pagar todos los salarios.')
        db.commit()
    return f'Jornada pagada: {total:.2f} de oro.'


def recover(hero_id):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _playing(db)
        changed=db.execute("UPDATE Aventurero SET estado='disponible' WHERE id=? AND estado='herido'",(int(hero_id),))
        if changed.rowcount!=1: raise GameError('Este héroe no está herido.')
        db.commit()
    return 'El aventurero descansó y vuelve a estar disponible.'
