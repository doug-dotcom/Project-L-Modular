$ErrorActionPreference = "Stop"

Write-Host "`n=== L RESTORE SYSTEM ===" -ForegroundColor Cyan

$CheckpointRoot = "C:\Shine_L_CHECKPOINTS"

$Latest = Get-ChildItem $CheckpointRoot -Directory |
Sort-Object LastWriteTime -Descending |
Select-Object -First 1

if (!$Latest) {
    throw "No checkpoints found."
}

Write-Host "Latest checkpoint found:" -ForegroundColor Green
Write-Host $Latest.FullName -ForegroundColor White

Write-Host "`nStopping runtime..." -ForegroundColor Yellow

Get-Process python -ErrorAction SilentlyContinue |
Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

Write-Host "`nRestoring checkpoint..." -ForegroundColor Yellow

robocopy `
    $Latest.FullName `
    "C:\Shine_L" `
    /MIR `
    /R:1 `
    /W:1 `
    /XD __pycache__ .git .venv node_modules |
Out-Null

Write-Host "`nRestarting runtime..." -ForegroundColor Green

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd 'C:\Shine_L'; python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload"
)

Start-Sleep -Seconds 5

Write-Host "`nRestarting UI..." -ForegroundColor Green

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd 'C:\Shine_L\ui'; python -m http.server 5050"
)

Start-Sleep -Seconds 3

Start-Process "http://127.0.0.1:5050"

Write-Host "`nL RESTORE COMPLETE 👊" -ForegroundColor Cyan
