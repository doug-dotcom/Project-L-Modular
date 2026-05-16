# Start API Server (8000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Shine_L; python -m uvicorn api.server:app --reload --port 8000"

# Wait a second so API starts first
Start-Sleep -Seconds 2

# Start UI Server (5500)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Shine_L\ui; python -m http.server 5500"

# Open browser tabs
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8000"
Start-Process "http://127.0.0.1:5500"
