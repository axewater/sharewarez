@echo off

cd /d "%~dp0"

call venv\Scripts\activate.bat

echo Starting SharewareZ with uvicorn...

REM Run complete startup initialization once before starting workers
python -c "from modules.startup_init import run_complete_startup_initialization; import sys; exit(1) if not run_complete_startup_initialization() else print('Startup initialization completed')"

if %errorlevel% neq 0 (
    echo Startup initialization failed, but continuing...
    exit /b 1
)

REM Ensure environment variables are set for worker processes
set SHAREWAREZ_MIGRATIONS_COMPLETE=true
set SHAREWAREZ_INITIALIZATION_COMPLETE=true

REM Start uvicorn with workers (migrations already complete)
uvicorn asgi:asgi_app --host 0.0.0.0 --port 5006 --workers 4