import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import OpenAI

# =========================================
# APP
# =========================================

app = FastAPI()

# =========================================
# CORS
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================
# OPENAI
# =========================================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# =========================================
# REQUEST MODEL
# =========================================

class ChatRequest(BaseModel):
    message: str

# =========================================
# ROOT
# =========================================

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Project L"
    }

# =========================================
# CHAT
# =========================================

@app.post("/chat")
def chat(req: ChatRequest):

    message = req.message

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        reply = response.choices[0].message.content

    except Exception as e:

        print(f"OPENAI ERROR: {e}")

        reply = "AI Error: Connection error."

    return {
        "reply": reply,
        "memory_wired": True,
        "memory_stats": {
            "identity": 0,
            "episodic": 0,
            "emotional": 0,
            "structured": 0,
            "session": 12
        }
    }
