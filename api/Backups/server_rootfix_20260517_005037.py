from openai import OpenAI

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from orchestration.runtime_bootstrap import (
    build_runtime_stack,
    build_runtime_status
)

from services.runtime_endpoints import (
    router as runtime_router
)

from utils.logger import (
    log_info,
    log_error,
    log_exception
)

# =====================================================
# LOAD ENV
# =====================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# =====================================================
# ROOT PATH
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# =====================================================
# MEMORY ENGINE
# =====================================================

from core.memory_engine import (
    build_memory_context,
    save_memory,
    memory_stats
)

# =====================================================
# OPENAI
# =====================================================

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = None

try:

    if OPENAI_API_KEY:

        client = OpenAI(
            api_key=OPENAI_API_KEY
        )

        log_info("OPENAI CLIENT INITIALIZED")

    else:

        log_error("OPENAI_API_KEY MISSING")

except Exception as e:

    log_exception(f"OPENAI INIT FAILED: {e}")

# =====================================================
# SERVER START
# =====================================================

log_info("PROJECT L SERVER STARTING")

# =====================================================
# TEGAN RUNTIME STACK
# =====================================================

runtime_stack = build_runtime_stack()

# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="Project L",
    version="1.0.0"
)

# =====================================================
# APP STATE
# =====================================================

app.state.runtime_stack = runtime_stack

# =====================================================
# ROUTERS
# =====================================================

app.include_router(runtime_router)

# =====================================================
# CORS
# =====================================================


# =====================================================
# UI STATIC
# =====================================================

UI_PATH = ROOT / "ui"

app.mount("/ui", StaticFiles(directory=UI_PATH), name="ui")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# REQUEST MODEL
# =====================================================

class ChatRequest(BaseModel):
    message: str

# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():

    return {
        "status": "online",
        "service": "Project L",
        "docs": "/docs"
    }

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
def health():

    log_info("Health check requested")

    return {
        "status": "ok",
        "openai_ready": bool(client),
        "model": MODEL,
        "memory_stats": memory_stats()
    }

# =====================================================
# CHAT
# =====================================================

@app.post("/chat")
def chat(req: ChatRequest):

    user_message = req.message.strip()

    log_info(f"CHAT REQUEST: {user_message[:80]}")

    # -------------------------------------------------
    # SAVE USER MEMORY
    # -------------------------------------------------

    save_memory(
        "session",
        {
            "role": "user",
            "content": user_message
        }
    )

    # -------------------------------------------------
    # MEMORY CONTEXT
    # -------------------------------------------------

    memory_context = build_memory_context(limit=15)

    system_prompt = f"""
You are L.

You are grounded, calm, practical and supportive.

Use memory naturally when relevant.

MEMORY:
{memory_context}
"""

    # -------------------------------------------------
    # OPENAI CHECK
    # -------------------------------------------------

    if not client:

        reply = "L is online but OpenAI is not connected."

    else:

        try:

            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                temperature=0.7
            )

            reply = response.choices[0].message.content

        except Exception as e:

            log_exception(f"CHAT FAILURE: {e}")

            reply = f"AI ERROR: {str(e)}"

    # -------------------------------------------------
    # SAVE ASSISTANT MEMORY
    # -------------------------------------------------

    save_memory(
        "session",
        {
            "role": "assistant",
            "content": reply
        }
    )

    # -------------------------------------------------
    # RESPONSE
    # -------------------------------------------------

    return {
        "reply": reply,
        "memory_wired": True,
        "memory_stats": memory_stats()
    }

# =====================================================
# ROUTES
# =====================================================

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
