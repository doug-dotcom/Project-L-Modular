$ErrorActionPreference = "Stop"

Write-Host "`n=== QUICK L CHECKPOINT ===" -ForegroundColor Cyan

$Root = "C:\Shine_L"

$CheckpointRoot = "C:\Shine_L_CHECKPOINTS"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$BackupPath = Join-Path `
    $CheckpointRoot `
    ("CHECKPOINT_" + $Timestamp)

New-Item -ItemType Directory -Force -Path $BackupPath | Out-Null

robocopy `
    $Root `
    $BackupPath `
    /MIR `
    /R:1 `
    /W:1 `
    /XD __pycache__ .git .venv node_modules backups |
Out-Null

Write-Host "`nCheckpoint created:" -ForegroundColor Green
Write-Host $BackupPath -ForegroundColor White
