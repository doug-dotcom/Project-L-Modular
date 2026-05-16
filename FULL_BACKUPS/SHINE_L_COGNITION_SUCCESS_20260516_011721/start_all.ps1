# Start API Server (correct path)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Shine_L\api; uvicorn server:app --reload --port 8000"

# Wait for API
Start-Sleep -Seconds 2

# Start UI server
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Shine_L\ui; python -m http.server 5500"

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8000/docs"
Start-Process "http://127.0.0.1:5500"
