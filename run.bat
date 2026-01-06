@echo off
title PDF to Website Automation
echo ========================================
echo    PDF to Website Automation Tool
echo ========================================
echo.
echo Starting the application...
echo.

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the GUI application
python -m script.gui

if %ERRORLEVEL% neq 0 (
    echo.
    echo Error: Failed to start the application.
    echo Make sure Python is installed and all dependencies are available.
    echo.
    pause
)

