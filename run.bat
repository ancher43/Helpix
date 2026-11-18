@echo off
title HelpDesk Knowledge Base
cd /d "D:\VKR\backend"

if not exist "D:\VKR\venv\Scripts\python.exe" (
    echo [ERROR] Python venv not found in D:\VKR\venv
    pause
    exit /b 1
)

echo =========================================================================
echo    HelpDesk Knowledge Base - Hybrid Search and Gap Clustering
echo =========================================================================
echo.
echo  Web Interface: http://localhost:8000
echo  API Docs (Swagger UI): http://localhost:8000/docs
echo.
echo =========================================================================
echo.

"D:\VKR\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
