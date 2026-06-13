@echo off
title ARIA — AI Study Assistant
color 0A

echo.
echo   ========================================
echo     ARIA - AI Study Assistant v2.0
echo   ========================================
echo.

:: Check Ollama
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Ollama not found.
    echo         Install from: https://ollama.com
    pause
    exit /b 1
)

:: Start Ollama
echo [1/4] Starting Ollama...
start /min "Ollama" ollama serve
timeout /t 3 /nobreak > nul

:: Check and pull models
echo [2/4] Checking AI models...
ollama list | findstr /i "qwen3" > nul
if %errorlevel% neq 0 (
    echo       Pulling qwen3:8b (this may take a while)...
    ollama pull qwen3:8b
)

:: Backend
echo [3/4] Starting Python backend...
cd /d "%~dp0backend"
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
start /min "ARIA Backend" python -m uvicorn main:app --host 0.0.0.0 --port 8000

timeout /t 5 /nobreak > nul

:: Frontend
echo [4/4] Starting frontend...
cd /d "%~dp0frontend"
if not exist node_modules (
    echo       Installing npm packages (first run only)...
    npm install
)
start /min "ARIA Frontend" npm run dev

timeout /t 4 /nobreak > nul

:: Open browser
echo.
echo   ========================================
echo     ARIA is ready!
echo     Opening: http://localhost:5173
echo   ========================================
echo.

start http://localhost:5173

echo   Press any key to stop ARIA...
pause > nul

taskkill /f /fi "WINDOWTITLE eq Ollama*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq ARIA*" > nul 2>&1
