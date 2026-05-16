# =====================================================
# Start-Guardian.ps1
# AODS 61
# =====================================================

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "STARTING L GUARDIAN LOOP" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

Set-Location "C:\Shine_L"

python guardian_loop.py

