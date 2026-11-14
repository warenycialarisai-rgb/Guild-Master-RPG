# Guild Master RPG — V3.3 (Flask + Dark Forest)

Paquete listo para añadir al repositorio del **Grupo 6**.
**No incluye `gremioDDLg6.sql` ni lo sustituye:** se utiliza **exactamente** el que ya existe en la raíz de GitHub.

## Archivos y procedencia

- Servidor Flask: `app.py`, `database.py`, `game.py`, `forest_bridge.py`.
- Pantallas: `templates/` y `static/css/`.
- Dark Forest Phaser 3 compilado: `static/darkforest/`. **No hace falta Node.js ni instalar Dark Forest en Railway**.
- `railway.json`, `.python-version`, `requirements.txt`: despliegue Python.
- `iniciar_local.bat`: ejecutar el mismo código en Windows; necesita Python 3.10+ y el SQL original en la carpeta.

No subir partidas `*.db`, carpetas `.venv/`, archivos `.env` ni copias del SQL.

## Desplegar en Railway

En el proyecto existente **JeronimoEducativo**, crear **un nuevo servicio** llamado `guild-master-informatica`, enlazado a `warenycialarisai-rgb/proyecto-torneo-preguntas` rama `main`. **No reemplazar** el servicio `JeronimoEducativo`.

1. Copiar el contenido de este ZIP a la raíz local de `proyecto-torneo-preguntas`, junto al `gremioDDLg6.sql` que ya está en GitHub. Verificar que el SQL NO aparezca como modificado en GitHub Desktop. Commit y Push.
2. En Railway: proyecto JeronimoEducativo → New Service → GitHub Repo → seleccionar el repositorio del grupo, rama `main`.
3. Crear y montar un volumen **exclusivo para Guild Master** en `/data`.
4. Configurar variables del servicio (no en Git):
   - `DB_PATH=/data/gremio.db`
   - `APP_PASSWORD=` contraseña fuerte, individual para el juego.
   - `SECRET_KEY=` clave aleatoria larga y estable. Cambiarla invalida sesiones.
   - Railway define `PORT` y `RAILWAY_ENVIRONMENT` automáticamente.
5. Desplegar. El inicio crea la base SQLite **solo si no existe**. Comprobar `/health` → `{"status":"ok"}`.
6. En Settings → Networking → Generate Domain, generar la URL `*.up.railway.app`. Testear inicio de sesión, menú y una misión.

**Importante:** un volumen persiste datos entre despliegues, pero no sincroniza partidas con Windows y no sustituye una copia de seguridad.

## Dominio JeronimoEducativo

`jeronimoeducativo.com` ya apunta al servicio `JeronimoEducativo`. Un servicio adicional **no obtiene automáticamente** la ruta `/informatica` por estar en el mismo proyecto Railway.

Alternativa rápida y segura: configurar el dominio personalizado **`informatica.jeronimoeducativo.com`** para el servicio Guild Master, agregando los registros DNS que Railway indique.

Si la URL **`https://jeronimoeducativo.com/informatica`** es imprescindible, hay que añadir una ruta o un proxy en el repositorio **separado** `jmvelezo/JeronimoEducativo`, actualmente la aplicación Flask principal. No cambiar este proyecto sin realizar respaldo y probar la integración. El proxy debe transportar `SCRIPT_NAME`/prefijo correctamente para enlaces, estáticos, cookies y POST del juego; un mero CNAME no permite enrutar por rutas URL.

## Ejecución local

Con el SQL del repositorio en la misma carpeta, doble clic en `iniciar_local.bat`; navegar a `http://127.0.0.1:5000`.
La base local se crea en `data/gremio.db`; **no** se sincroniza automáticamente con Railway.

## Créditos y licencias

Dark Forest: © Nick Haralampopoulos, código bajo **MIT**. Se conserva la licencia `static/darkforest/ORIGINAL_LICENSE` y el README original. Origen: <https://github.com/macnick/RPG-game>. El juego se distribuye aquí con sus recursos gráficos originales, de **proveedores externos** cuyas licencias no se han verificado individualmente; dar crédito **no equivale** a disponer de permiso de redistribución. **No publicar esta versión en un repositorio público ni en un sitio público sin verificar previamente los permisos de los gráficos.** El archivo de música se ha sustituido por silencio.

## Estado de pruebas

El paquete se depuró eliminando entorno, datos y archivos obsoletos. Antes de usarlo con usuarios reales, validar una partida completa, carga de sprites, combate y almacenamiento persistente en Railway. El motor Phaser original es client-side: el resultado no tiene protección antitrampas fuerte.
