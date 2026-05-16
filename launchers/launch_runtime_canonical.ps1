# =====================================================
# PROJECT L — CANONICAL RUNTIME LAUNCHER
# =====================================================

$env:PYTHONPATH = 'C:\Shine_L'

cd C:\Shine_L

uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
