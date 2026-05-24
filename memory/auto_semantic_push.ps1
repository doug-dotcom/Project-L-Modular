
# =====================================================
# PROJECT L AUTO SEMANTIC PUSH
# =====================================================

Set-Location "C:\Shine_L"

# =====================================================
# CHECK FOR DOMAIN CHANGES ONLY
# =====================================================

$changes = git status --porcelain memory/domains

if (!$changes) {

    Write-Host "[SKIP] No semantic memory changes"

    exit
}

Write-Host ""
Write-Host "[OK] Semantic memory changes detected"
Write-Host ""

# =====================================================
# STAGE DOMAIN FILES ONLY
# =====================================================

git add memory/domains

# =====================================================
# COMMIT
# =====================================================

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

git commit -m "Auto semantic sync $stamp"

# =====================================================
# PUSH
# =====================================================

git push

Write-Host ""
Write-Host "[OK] Semantic cognition synced"
Write-Host ""

