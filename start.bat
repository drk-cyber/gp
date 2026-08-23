@echo off
title A-share Backtest System
cd /d C:\gp

echo ==========================================
echo    A-share Backtest System
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [Error] Python not found. Please install Python 3.10+
    echo.
    pause
    exit /b 1
)

echo Starting server, browser will open automatically...
echo URL: http://127.0.0.1:8000
echo Close this window to stop the server.
echo.

start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"

python webapp.py

echo.
echo Server stopped.
pause
