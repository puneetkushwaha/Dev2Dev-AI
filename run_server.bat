@echo off
SETLOCAL
cd /d "%~dp0"
echo ===================================================
echo   DevElevate AI Service - Automated Startup
echo ===================================================
echo.

if not exist "venv" (
    echo [ERROR] Virtual environment 'venv' not found!
    echo Please make sure you are in the ai-service directory.
    pause
    exit /b
)

echo [1/2] Activating Virtual Environment...
call venv\Scripts\activate.bat

echo [2/2] Starting Gemini AI Service...
python main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Server failed to start. 
    echo Please check if another instance is already running on port 8000.
    pause
)
pause
