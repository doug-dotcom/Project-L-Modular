# =====================================================
# PROJECT L — STABLE CORE LAUNCHER
# =====================================================

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "PROJECT L — STABLE CORE" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

cd C:\Shine_L

uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
