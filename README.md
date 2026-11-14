# Guild Master RPG — Informática II, Grupo 6

## ¿De qué trata?

Este es nuestro proyecto para el trabajo integrador de Informática II.
Elegimos Guild Master RPG, un juego donde administramos un gremio de aventureros. La idea es contratar héroes, comprarles equipamiento, enviarlos a misiones y administrar el oro del gremio.
Tenemos tres clases de aventureros: guerreros, magos y arqueros. Cada uno tiene su nivel, salario y estado.

Para completar las misiones hay que formar un equipo de hasta tres aventureros y entrar al Bosque Oscuro, donde se desarrolla el combate. Según el resultado, la misión se completa o falla, y se actualizan los datos del gremio.

El objetivo es llegar a **5 misiones completadas** para ganar la temporada. Si se terminan las misiones disponibles sin alcanzar ese objetivo, perdemos.

## Tecnologías que usamos (apoyo IA)

- **Python y Flask:** para la aplicación y las distintas pantallas (elejimos flask por su facilidad para manejar elementos web con python y la coneccion con sqlite).
- **SQLite:** para guardar los aventureros, las misiones, el inventario y los movimientos del tesoro.
- **HTML, CSS y JavaScript:** para la interfaz.
- **Phaser / Dark Forest:** para la parte de combate. (juego opensource bajo licencia MIT adaptado a nuestra propuesta, Sólo funciona como experiencia, en lógica sólo determina Victoria si o no. funciona como un interrupotor interactivo, no modifica ni altera directamente la base de datos.) 
- **GitHub:** para guardar y compartir el código.
- **Railway:** para tener el juego publicado en internet.


## Cómo instalarlo en otra computadora

Para ejecutarlo localmente necesitamos tener instalado **Python 3.10 o superior** (usamos Python 3.11). También necesitamos conexión a internet para instalar las dependencias la primera vez.

1. Descargar el proyecto desde GitHub:

   https://github.com/warenycialarisai-rgb/proyecto-torneo-preguntas

2. Entrar en **Code → Download ZIP**, descargarlo y extraer la carpeta.

3. En Windows, abrir el archivo `iniciar_local.bat`.

4. El archivo prepara el entorno de Python, instala lo necesario y después inicia el servidor.

5. Cuando termine de iniciar, abrir esta dirección en el navegador:

   **http://127.0.0.1:5000**

Hay que dejar abierta la ventana del servidor mientras jugamos.

Si se quiere iniciar manualmente, desde la carpeta del proyecto se pueden ejecutar estos comandos:

```bash
python -m venv .venv
```

Activar el entorno, instalar las dependencias y ejecutar:

```bash
pip install -r requirements.txt
python app.py
```

## ¿Cómo funciona la base de datos?

El archivo principal es `gremioDDLg6.sql`. Ahí tenemos las seis tablas, los datos iniciales, las restricciones, las consultas, la vista y la prueba de transacción con ROLLBACK.

Las tablas son:

- Aventurero
- Mision
- Equipamiento
- Tesoro
- Asignacion_Mision
- Inventario_Aventurero

Las dos últimas relacionan a los aventureros con sus misiones y equipamientos.

No hace falta crear la base manualmente. Al iniciar el programa, `database.py` utiliza nuestro archivo SQL para generar la base SQLite si todavía no existe.

Los archivos se guardan en la carpeta `data`. Cada navegador tiene su propia partida, así que dos personas pueden entrar al juego sin modificar los aventureros o el tesoro de la otra.

**Importante:** las partidas se identifican mediante cookies. Si se borran, o cambia la clave de sesión del servidor, se puede perder el acceso a la partida anterior aunque el archivo SQLite siga guardado. Para conservar la identificación entre reinicios locales hay que configurar una `SECRET_KEY` fija.

## Cómo jugar

Primero entramos al Salón del Gremio, donde podemos ver el oro disponible, los aventureros y las misiones.

Desde **Aventureros** podemos contratar nuevos héroes. En **Armería** compramos y equipamos objetos, siempre que tengamos oro suficiente.

Después entramos a **Misiones**, elegimos una misión pendiente y asignamos entre uno y tres aventureros disponibles.

Con la cuadrilla formada podemos entrar al Bosque Oscuro. Al terminar el combate, el resultado se registra en SQLite. Si ganamos, recibimos la recompensa y experiencia correspondiente.

En **Tesoro** podemos consultar los ingresos y gastos del gremio, incluyendo las compras y los salarios.

Las operaciones que modifican varios datos se realizan mediante transacciones para evitar cambios incompletos.

## Versión en internet

También publicamos el juego en Railway para que otras personas puedan probarlo sin instalar nada.

Se puede ingresar desde:

https://jeronimoeducativo.com/informatica

Ese enlace redirige al proyecto independiente:

https://guild-master-production.up.railway.app/

No se necesita usuario ni contraseña. Cada navegador tiene su partida y la información se guarda en SQLite dentro del almacenamiento persistente de Railway.

## Archivos principales

- `gremioDDLg6.sql`: estructura, datos y consultas SQL.
- `app.py`: aplicación Flask y sus rutas.
- `database.py`: conexión e inicialización de SQLite.
- `game.py`: acciones y funcionamiento del gremio.
- `forest_bridge.py`: conexión entre las misiones y Dark Forest.
- `templates/`: pantallas HTML.
- `static/`: estilos, imágenes y archivos del juego.
- `requirements.txt`: dependencias de Python.
- `iniciar_local.bat`: inicio automático en Windows.
- `railway.json`: configuración para publicar en Railway.

## Sobre el desarrollo

El trabajo lo hicimos tomando como base el modelo de datos y las reglas que definimos para el gremio.

Usamos herramientas de IA para ayudarnos con la programación, la interfaz y la corrección de errores. La aplicación se desarrolló respetando las tablas y columnas del archivo SQL.

El proyecto se fue modificando durante el desarrollo. Primero trabajamos en la base de datos y después fuimos agregando la gestión del gremio, las pantallas, el combate y finalmente la posibilidad de que distintas personas tengan partidas independientes.
