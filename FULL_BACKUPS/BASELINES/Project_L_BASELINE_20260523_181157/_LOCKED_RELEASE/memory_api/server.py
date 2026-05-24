from fastapi import FastAPI
import json, os

app = FastAPI()

BASE = r"C:\Shine_L\memory"

def load(file):
    path = os.path.join(BASE, file)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save(file, data):
    path = os.path.join(BASE, file)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.get("/memory/{file}")
def get_memory(file: str):
    return load(file)

@app.post("/memory/{file}")
def update_memory(file: str, payload: dict):
    data = load(file)
    data.update(payload)
    save(file, data)
    return {"status": "updated", "file": file}

@app.get("/")
def root():
    return {"status": "Shine Memory Bridge v2 Live"}
