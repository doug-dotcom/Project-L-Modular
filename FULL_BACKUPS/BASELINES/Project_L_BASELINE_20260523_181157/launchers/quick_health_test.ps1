# =====================================================
# PROJECT L — QUICK HEALTH TEST
# =====================================================

try {

    Invoke-RestMethod 
        -Uri "http://127.0.0.1:8000/health"

}
catch {

    Write-Host ""
    Write-Host "SERVER OFFLINE" -ForegroundColor Red
    Write-Host ""
}
