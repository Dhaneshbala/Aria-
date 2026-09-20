@echo off
title Study Buddy — AI Study Assistant
color 0A

echo.
echo   ========================================
echo     Study Buddy - AI Study Assistant v2.0
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

:: Check and pull models (gemma4 + nomic)
echo [2/4] Checking AI models (gemma4 + nomic)...
ollama list | findstr /i "gemma" > nul
if %errorlevel% neq 0 (
    echo       Pulling gemma4:e4b-mlx (this may take a while)...
    ollama pull gemma4:e4b-mlx
)
ollama list | findstr /i "nomic" > nul
if %errorlevel% neq 0 (
    echo       Pulling nomic-embed-text...
    ollama pull nomic-embed-text
)

:: Backend
echo [3/4] Starting Python backend...
cd /d "%~dp0backend"
if not exist venv (
    python -m venv venv
)
if exist "..\.venv\Scripts\activate.bat" (
    call "..\.venv\Scripts\activate.bat"
) else (
    call venv\Scripts\activate.bat
)
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)
start /min "Study Buddy Backend" python -m uvicorn main:app --host 127.0.0.1 --port 8000

timeout /t 5 /nobreak > nul

:: Frontend
echo [4/4] Starting frontend...
cd /d "%~dp0frontend"
if not exist node_modules (
    echo       Installing npm packages (first run only)...
    npm install
)
start /min "Study Buddy Frontend" npm run dev

timeout /t 4 /nobreak > nul

:: Open browser
echo.
echo   ========================================
echo     Study Buddy is ready!
echo     Opening: http://localhost:5173
echo   ========================================
echo.

start http://localhost:5173

echo   Press any key to stop Study Buddy...
pause > nul

taskkill /f /fi "WINDOWTITLE eq Ollama*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Study Buddy*" > nul 2>&1
