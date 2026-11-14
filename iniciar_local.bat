@echo off
setlocal
cd /d "%~dp0"
title Guild Master RPG - servidor local

echo =====================================
echo       GUILD MASTER RPG - LOCAL
echo =====================================

if not exist "app.py" (
    echo ERROR: No se encuentra app.py en esta carpeta.
    pause
    exit /b 1
)
if not exist "gremioDDLg6.sql" (
    echo ERROR: Falta gremioDDLg6.sql junto a app.py.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparando el entorno Python...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Intentando con el comando python...
        python -m venv .venv
    )
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno. Comproba Python 3.10 o superior.
        pause
        exit /b 1
    )
)

echo Instalando o verificando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

set "DB_PATH=%CD%\data\gremio.db"
set "APP_PASSWORD="

echo.
echo Iniciando servidor. Mantené esta ventana abierta.
echo Cuando aparezca Running on http://127.0.0.1:5000
echo abri esa direccion en el navegador.
echo.
".venv\Scripts\python.exe" app.py

echo.
echo El servidor se detuvo. Revisa los mensajes de error anteriores.
pause
