@echo off
setlocal

set "ROOT=%~dp0"
set "PROJECT=%ROOT%smartpoultry"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "LOG=%ROOT%server.cmd.log"
set "MIGRATION_LOG=%ROOT%server.migrate.log"

if not exist "%PYTHON%" (
    set "PYTHON=%ROOT%venv\Scripts\python.exe"
)

if not exist "%PYTHON%" (
    set "PYTHON=py"
)

if not exist "%PROJECT%\manage.py" (
    echo Django manage.py was not found: %PROJECT%\manage.py
    exit /b 1
)

cd /d "%PROJECT%" || exit /b 1

echo [%date% %time%] Checking database migrations >> "%MIGRATION_LOG%"
"%PYTHON%" manage.py migrate --noinput >> "%MIGRATION_LOG%" 2>&1
if errorlevel 1 (
    echo Database setup failed. See "%MIGRATION_LOG%" for details.
    exit /b 1
)

netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo SMARTPOULTRY is already running at http://127.0.0.1:8000/
    exit /b 0
)

echo [%date% %time%] Starting SMARTPOULTRY at http://127.0.0.1:8000/ >> "%LOG%"
"%PYTHON%" manage.py runserver 127.0.0.1:8000 >> "%LOG%" 2>&1
