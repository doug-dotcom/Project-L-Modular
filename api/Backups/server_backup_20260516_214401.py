import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from orchestration.runtime_bootstrap import (
    build_runtime_stack,
    build_runtime_status
)

from services.runtime_endpoints import router as runtime_router

from utils.logger import (
    log_info,
    log_error,
    log_exception
)

# Runtime API

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.memory_engine import (
    build_memory_context,
    save_memory,
    memory_stats
)

try:
    from openai import OpenAI
except:
    OpenAI = None

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = None

if OpenAI and OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

log_info("PROJECT L SERVER STARTING")


# =====================================================
# TEGAN RUNTIME STACK
# =====================================================

runtime_stack = build_runtime_stack()


app = FastAPI(
    title="Project L",
    version="1.0.0"
)

# Runtime stack binding
app.state.runtime_stack = runtime_stack


app.include_router(runtime_router)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():

    return {
        "status": "online",
        "docs": "/docs"
    }

@app.get("/health")
def health():

    log_info("Health check requested")

    return {
        "status": "ok",
        "memory_stats": memory_stats(),
        "openai_ready": bool(client)
    }

@app.post("/chat")
def chat(req: ChatRequest):

    user_message = req.message.strip()

    log_info(f"CHAT REQUEST: {user_message[:80]}")

    save_memory(
        "session",
        {
            "role": "user",
            "content": user_message
        }
    )

    memory_context = build_memory_context(limit=15)

    system_prompt = f'''
You are L.

You are grounded, calm, practical and supportive.

Use memory naturally when relevant.

MEMORY:
{memory_context}
'''

    if not client:

        reply = (
            "L is online but OPENAI_API_KEY is missing."
        )

    else:

        try:

            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role":"system",
                        "content":system_prompt
                    },
                    {
                        "role":"user",
                        "content":user_message
                    }
                ],
                temperature=0.7
            )

            reply = response.choices[0].message.content

        except Exception as e:

            reply = f"AI Error: {str(e)}"

    save_memory(
        "session",
        {
            "role": "assistant",
            "content": reply
        }
    )

    return {
        "reply": reply,
        "memory_stats": memory_stats(),
        "memory_wired": True
    }

@app.get("/routes")
def routes():

    return {
        "routes": [
            "/",
            "/health",
            "/chat",
            "/routes",
            "/docs"
        ]
    }



