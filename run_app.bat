@echo off
setlocal
title Medical AI Chatbot Launcher

echo ===================================================
echo 🏥 Medical AI Chatbot - Startup Script
echo ===================================================

cd /d "%~dp0"

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Check/Create Virtual Environment
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ❌ Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate Virtual Environment
echo 🚀 Activating virtual environment...
call .venv\Scripts\activate.bat

:: Install Requirements if needed
if not exist ".venv\Lib\site-packages\flask" (
    echo 📦 Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ❌ Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo ✅ Dependencies look installed.
)

:: Run the Application
echo.
echo 🌐 Starting Server...
echo The app will be available at http://localhost:8000
echo.
python web/app.py

if %errorlevel% neq 0 (
    echo ❌ Application exited with error.
)

pause
