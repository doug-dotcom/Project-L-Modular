# ============================================================
# SHINE L MODULAR SMOKE TEST
# Run this after L is started locally.
# ============================================================

$Base = "http://127.0.0.1:8000"

Write-Host ""
Write-Host "Testing Shine L local endpoints..."
Write-Host ""

try {
    Invoke-RestMethod "$Base/" | ConvertTo-Json -Depth 5
    Write-Host "ROOT OK"
} catch {
    Write-Host "ROOT FAILED"
    Write-Host $_.Exception.Message
}

try {
    Invoke-RestMethod "$Base/system/stability" | ConvertTo-Json -Depth 5
    Write-Host "SYSTEM STABILITY OK"
} catch {
    Write-Host "SYSTEM STABILITY FAILED"
    Write-Host $_.Exception.Message
}

try {
    Invoke-RestMethod "$Base/memory/audit-v2" | ConvertTo-Json -Depth 8
    Write-Host "MEMORY AUDIT V2 OK"
} catch {
    Write-Host "MEMORY AUDIT V2 FAILED"
    Write-Host $_.Exception.Message
}

Write-Host ""
Write-Host "Smoke test complete."
