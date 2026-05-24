# ============================================================
# PROJECT L STARTUP LAUNCHER
# STAGE 3 LOCAL BETA
# ============================================================

$ErrorActionPreference = "SilentlyContinue"

$Root = "C:\Shine_L"

Write-Host ""
Write-Host "============================================================"
Write-Host " STARTING PROJECT L"
Write-Host "============================================================"

# ------------------------------------------------------------
# STOP OLD PYTHON
# ------------------------------------------------------------

Write-Host "Stopping existing Python runtimes..."

Get-Process python |
Stop-Process -Force

Start-Sleep -Seconds 2

# ------------------------------------------------------------
# START RUNTIME
# ------------------------------------------------------------

Write-Host "Starting runtime..."

Start-Process powershell `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$Root'; python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload"
    )

Start-Sleep -Seconds 6

# ------------------------------------------------------------
# START UI
# ------------------------------------------------------------

Write-Host "Starting UI..."

Start-Process powershell `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$Root\ui'; python -m http.server 5050"
    )

Start-Sleep -Seconds 3

# ------------------------------------------------------------
# OPEN BROWSER
# ------------------------------------------------------------

Start-Process "http://127.0.0.1:5050"

Write-Host ""
Write-Host "============================================================"
Write-Host " PROJECT L ONLINE"
Write-Host "============================================================"
Write-Host "Runtime: http://127.0.0.1:8000/docs"
Write-Host "UI:      http://127.0.0.1:5050"
Write-Host "============================================================"
