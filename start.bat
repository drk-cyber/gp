@echo off
title A-share Backtest System
cd /d C:\gp

set "PY=C:\Users\24331\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PY%" (
    echo [Error] Python not found:
    echo   %PY%
    echo.
    echo Please install dependencies and run: python webapp.py
    pause
    exit /b 1
)

echo Starting server, browser will open automatically...
echo URL: http://127.0.0.1:8000
echo Close this window to stop the server.
echo.

start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"

"%PY%" webapp.py

echo.
echo Server stopped.
pause
