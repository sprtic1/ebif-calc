@echo off
title EID Project Manager — Launcher
echo.
echo   EID Project Manager
echo   ====================
echo.
echo   Starting Flask backend on http://localhost:5000 ...
start "EID Backend" cmd /k "cd /d %~dp0app\backend && python app.py"

echo   Starting Vite frontend on http://localhost:3000 ...
start "EID Frontend" cmd /k "cd /d %~dp0app\frontend && npm run dev"

echo.
echo   Both servers launching in separate windows.
echo   Open http://localhost:3000 in your browser.
echo.
pause
