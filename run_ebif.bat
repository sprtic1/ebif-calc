@echo off
title EBIF-CALC — Run the EBIF Report
color 0A

echo.
echo ============================================================
echo   EBIF-CALC — Ellis Building Intelligence Framework
echo   Run the EBIF Report (standalone — no Claude Code needed)
echo ============================================================
echo.

:: Change to the EBIF-CALC directory (where this bat file lives)
cd /d "%~dp0"

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12+ and add to PATH.
    pause
    exit /b 1
)

:: Run the extract pipeline
echo Starting EBIF Report...
echo.
python main.py extract

:: Check exit code
if errorlevel 1 (
    echo.
    echo [ERROR] Pipeline failed. Check the output above for details.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Done! Press any key to close.
echo ============================================================
pause >nul
