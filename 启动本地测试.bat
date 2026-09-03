@echo off
title MediaVault

echo ========================================
echo   MediaVault Local Test
echo ========================================
echo.

cd /d "%~dp0"

:: Check Python
set PYTHON=C:\Users\Win11\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

:: Setup backend venv
echo [1/3] Setting up backend...
cd /d "%~dp0backend"
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PYTHON%" -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt greenlet pydantic-settings
) else (
    call venv\Scripts\activate.bat
)

:: Start backend (port from backend/.env HTTP_PORT, default 8099)
echo [2/3] Starting backend...
start "MV-Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate.bat && set MV_RELOAD=1 && python run.py"

:: Start frontend
echo [3/3] Starting frontend on port 5173...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)
start "MV-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo   Backend:  http://127.0.0.1:8099
echo   Frontend: http://127.0.0.1:5173
echo   API Docs: http://127.0.0.1:8099/docs
echo ========================================
echo.
echo Press any key to stop all services...
pause >nul

taskkill /FI "WindowTitle eq MV-Backend*" /F >nul 2>&1
taskkill /FI "WindowTitle eq MV-Frontend*" /F >nul 2>&1
echo Done.
