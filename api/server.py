import os
import sys
import json

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

# =====================================================
# SERVER VX
# MAIN STREET
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

# =====================================================
# SHOPS
# =====================================================

from agents.rhee.rhee_v3 import (
    build_context_packet as build_rhee_packet
)

from agents.tegan.tegan import (
    route_message
)

from memory.continuity.live_short_term import (
    classify_short_term_domain,
    write_short_term_memory,
)
from memory.retrieval.cache_state import invalidate_recall_caches

try:
    from voice.speaker import speak
except Exception:
    def speak(text):
        return None

try:
    from core.cognition.brain_pipeline import (
        process_raw_memory
    )
except Exception:
    process_raw_memory = None

# =====================================================
# ENVIRONMENT
# =====================================================

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# =====================================================
# LOGGER / TOWN CLOCK
# =====================================================

def log(msg):
    print(f"{datetime.now().isoformat()} | {msg}")

def build_time_context():
    now = datetime.now(ZoneInfo("Australia/Brisbane"))

    return {
        "date": now.strftime("%A %d %B %Y"),
        "time": now.strftime("%I:%M %p"),
        "timezone": "Australia/Brisbane"
    }

# =====================================================
# FASTAPI
# =====================================================

app = FastAPI(
    title="Project L Server VX",
    version="server-vx-1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

UI_PATH = ROOT / "ui"

if UI_PATH.exists():
    app.mount(
        "/ui",
        StaticFiles(directory=UI_PATH),
        name="ui"
    )

# =====================================================
# MODELS
# =====================================================

class ChatRequest(BaseModel):
    message: str

# =====================================================
# MEMORY DEPOT
# =====================================================

def write_raw_catchall(role, content, source="chat"):
    try:
        if not supabase:
            return None

        payload = {
            "role": str(role),
            "source": str(source),
            "content": str(content),
            "metadata": {}
        }

        result = (
            supabase.table("raw_catchall")
            .insert(payload)
            .execute()
        )

        invalidate_recall_caches(raw=True)

        rows = result.data or []

        if rows:
            return rows[0]

        return None

    except Exception as e:
        log(f"RAW MEMORY ERROR: {e}")
        return None

def run_brain_pipeline(raw_row):
    try:
        if not process_raw_memory:
            return None

        if not raw_row or not isinstance(raw_row, dict):
            return None

        return process_raw_memory(raw_row)

    except Exception as e:
        log(f"BRAIN PIPELINE ERROR: {e}")
        return None

def write_live_short_term(table_name, role, content):
    result = write_short_term_memory(
        supabase,
        table_name,
        role,
        content,
    )

    if result.get("saved"):
        log(
            f"SHORT TERM SAVED -> {table_name} | "
            f"{role} | ID={result.get('id')}"
        )
    else:
        log(
            f"SHORT TERM SKIPPED -> {table_name} | "
            f"{role} | {result.get('reason')}"
        )

    return result

# =====================================================
# VOICE
# =====================================================

def voice_enabled():
    try:
        identity_file = ROOT / "memory" / "identity_core" / "l_identity.json"

        if not identity_file.exists():
            return True

        with open(identity_file, "r", encoding="utf-8") as f:
            identity = json.load(f)

        return identity.get("voice_enabled", True)

    except Exception:
        return True

# =====================================================
# ROOT / HEALTH
# =====================================================

@app.get("/")
def root():
    index_path = UI_PATH / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    return {
        "status": "Project L Server VX online"
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "server": "vx",
        "openai_ready": bool(client),
        "supabase_ready": bool(supabase),
        "rhee_ready": True,
        "tegan_ready": True,
        "main_street": True
    }

# =====================================================
# CHAT - MAIN STREET
# =====================================================

@app.post("/chat")
def chat(req: ChatRequest):
    user_message = (req.message or "").strip()

    if not user_message:
        return {
            "reply": "Please send me a message.",
            "server": "vx"
        }

    log(f"VX CHAT REQUEST: {user_message[:120]}")

    short_term_domain = classify_short_term_domain(user_message)
    short_term_user = write_live_short_term(
        short_term_domain,
        "user",
        user_message,
    )

    raw_user_row = write_raw_catchall(
        "user",
        user_message
    )

    run_brain_pipeline(raw_user_row)

    time_context = build_time_context()

    # =================================================
    # RHEE GIFT SHOP - MANDATORY ENTRY
    # =================================================

    try:
        rhee_packet = build_rhee_packet(user_message)
        rhee_context = rhee_packet.get("context", "")
        log(f"RHEE CONTEXT SIZE: {len(rhee_context)}")
        log(f"RHEE RECALL ACTIVE: {rhee_packet.get('recall_active')}")
    except Exception as e:
        log(f"RHEE ERROR: {e}")
        rhee_packet = {}
        rhee_context = "Rhee context unavailable."

    # =================================================
    # TEGAN TRAFFIC CONTROLLER
    # =================================================

    try:
        route = route_message(user_message)
        log(f"TEGAN ROUTE: {route}")
    except Exception as e:
        log(f"TEGAN ERROR: {e}")
        route = {
            "agent": "L Core",
            "handled": False,
            "reply": ""
        }

    if route.get("handled"):
        reply = route.get("reply", "")
    else:
        if not client:
            reply = "L is online but OpenAI is not connected."
        else:
            system_prompt = f"""
You are L.

CURRENT DATE:
{time_context["date"]}

CURRENT TIME:
{time_context["time"]}

TIMEZONE:
{time_context["timezone"]}

You are Doug's calm grounded companion.

You are the only voice Doug talks to.

Never speak as internal agents.

Project L town structure:
- Server VX is Main Street.
- Tegan is the traffic controller.
- Rhee is the mandatory entry gift shop for identity, learnings, continuity and recall.
- Brittany handles research.
- Emily handles email.
- Callie handles calendar.
- Tanya handles tasks.

RHEE CONTEXT PACKET:
{rhee_context}

ROUTE INFORMATION:
{route}

RESPONSE RULES:
- Use Rhee context naturally and accurately.
- If Rhee provides relevant memory, use it.
- For a specific factual question, prioritise Rhee's highest-scoring direct evidence.
- Prefer affirmative dated records over later questions or uncertainty replies.
- Do not say you have no memory if relevant context is present.
- Keep emotional and topic continuity.
- Join the dots, no more no less.
"""

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
                    temperature=0.6
                )

                reply = response.choices[0].message.content

            except Exception as e:
                log(f"OPENAI ERROR: {e}")
                reply = f"AI ERROR: {str(e)}"

    short_term_assistant = write_live_short_term(
        short_term_domain,
        "assistant",
        reply,
    )

    write_raw_catchall(
        "assistant",
        reply
    )

    if voice_enabled():
        try:
            speak(reply)
        except Exception as e:
            log(f"VOICE ERROR: {e}")

    return {
        "reply": reply,
        "server": "vx",
        "route": route,
        "rhee": {
            "context_size": len(rhee_context),
            "recall_active": rhee_packet.get("recall_active"),
            "short_term_domain": rhee_packet.get("short_term_domain")
        },
        "short_term": {
            "domain": short_term_domain,
            "user_saved": bool(short_term_user.get("saved")),
            "assistant_saved": bool(short_term_assistant.get("saved"))
        }
    }

# =====================================================
# END SERVER VX
# =====================================================
