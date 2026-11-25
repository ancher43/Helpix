Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "   Helpix - Knowledge Base & Hybrid Search" -ForegroundColor Cyan
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location "D:\VKR\backend"

$pythonPath = "D:\VKR\venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Host "[ОШИБКА] Окружение Python не найдено в D:\VKR\venv!" -ForegroundColor Red
    Pause
    Exit
}

Write-Host "Веб-интерфейс: http://localhost:8000" -ForegroundColor Green
Write-Host "Документация API: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""

& $pythonPath -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
