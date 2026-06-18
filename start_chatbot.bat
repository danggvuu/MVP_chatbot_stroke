@echo off
chcp 65001 >nul
:: ============================================================
:: 🧠 StrokeGuard AI - Khoi dong nhanh (Windows)
:: ============================================================

cd /d "%~dp0"

echo.
echo   🧠  ╔══════════════════════════════════════════╗
echo       ║     StrokeGuard AI - Khoi dong nhanh     ║
echo       ║   He thong Tu van So cuu Dot quy         ║
echo       ╚══════════════════════════════════════════╝
echo.

:: --- 1. Kiem tra Python ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   ❌  Python chua duoc cai dat!
    echo       Tai tai: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   ✅  %%i

:: --- 2. Tao virtual environment neu chua co ---
if not exist "venv" (
    echo   ⏳  Dang tao virtual environment...
    python -m venv venv
    echo   ✅  Da tao venv\
)

:: Kich hoat venv
call venv\Scripts\activate.bat
echo   ✅  Da kich hoat virtual environment

:: --- 3. Cai dat dependencies ---
echo   ⏳  Kiem tra va cai dat dependencies...
pip install -r requirements.txt -q 2>nul
echo   ✅  Dependencies da san sang

:: --- 4. Kiem tra knowledge base ---
if not exist "data\knowledge_base.json" (
    echo.
    echo   ⏳  Chua co knowledge base. Dang cao du lieu y khoa...
    python data_pipeline\scraper.py
    echo.
)
for /f %%a in ('python -c "import json; print(len(json.load(open('data/knowledge_base.json'))))" 2^>nul') do set CHUNK_COUNT=%%a
echo   ✅  Knowledge Base: %CHUNK_COUNT% phan doan y khoa

:: --- 5. Kiem tra Ollama ---
echo.
set "OLLAMA_MODEL=qwen2.5:3b"

where ollama >nul 2>&1
if %errorlevel% equ 0 (
    echo   ✅  Ollama da cai dat
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if %errorlevel% equ 0 (
        echo   ✅  Ollama server dang chay
        ollama list 2>nul | findstr /i "%OLLAMA_MODEL%" >nul
        if %errorlevel% neq 0 (
            echo   ⚠️  Model %OLLAMA_MODEL% chua tai. Dang tai...
            ollama pull %OLLAMA_MODEL%
        ) else (
            echo   ✅  Model %OLLAMA_MODEL% da san sang
        )
    ) else (
        echo   ⚠️  Ollama chua chay. Dang khoi dong...
        start /b ollama serve >nul 2>&1
        timeout /t 3 /nobreak >nul
        ollama list 2>nul | findstr /i "%OLLAMA_MODEL%" >nul
        if %errorlevel% neq 0 (
            echo   ⏳  Dang tai model %OLLAMA_MODEL% (lan dau co the mat vai phut^)...
            ollama pull %OLLAMA_MODEL%
        )
        echo   ✅  Ollama da khoi dong
    )
) else (
    echo   ⚠️  Ollama chua cai dat!
    echo       Tai tai: https://ollama.com/download
    echo       Sau khi cai, chay: ollama pull %OLLAMA_MODEL%
    echo.
    echo   ⏳  Server van se khoi dong nhung chatbot se khong tra loi duoc.
)

:: --- 6. Khoi dong server ---
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║  🚀  Khoi dong StrokeGuard AI Server... ║
echo   ║  📍  http://localhost:5080               ║
echo   ║  📄  API Docs: http://localhost:5080/docs║
echo   ║  ⏹   Nhan Ctrl+C de tat server          ║
echo   ╚══════════════════════════════════════════╝
echo.

:: Mo trinh duyet sau 2 giay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5080"

:: Chay FastAPI server
python main.py
