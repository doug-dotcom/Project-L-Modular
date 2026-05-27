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
from supabase import create_client
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# =====================================================
# BASIC LOGGER
# =====================================================

def log(msg):
    print(f"{datetime.now().isoformat()} | {msg}")

# =====================================================
# OPENAI
# =====================================================

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = None

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
    log("OPENAI CLIENT INITIALIZED")

# =====================================================
# SUPABASE
# =====================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    log("SUPABASE CONNECTED")

# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="Project L",
    version="clean-memory-1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_PATH = ROOT / "ui"

if UI_PATH.exists():
    app.mount("/ui", StaticFiles(directory=UI_PATH), name="ui")

# =====================================================
# MODELS
# =====================================================

class ChatRequest(BaseModel):
    message: str

# =====================================================
# RAW CATCHALL WRITER
# =====================================================

def write_raw_catchall(role, content, source="chat"):
    try:
        if not supabase:
            log("RAW CATCHALL SKIPPED: Supabase not connected")
            return False

        payload = {
            "role": str(role),
            "source": str(source),
            "content": str(content),
            "metadata": {}
        }

        supabase.table("raw_catchall").insert(payload).execute()

        log(f"RAW_CATCHALL WRITE OK: {role} -> {str(content)[:80]}")
        return True

    except Exception as e:
        log(f"RAW_CATCHALL WRITE ERROR: {e}")
        return False

# =====================================================
# MEMORY CONTEXT BUILDER
# =====================================================

def fetch_recent_raw(limit=20):
    try:
        if not supabase:
            return []

        result = (
            supabase
            .table("raw_catchall")
            .select("id,created_at,role,source,content")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        rows = result.data or []
        rows.reverse()
        return rows

    except Exception as e:
        log(f"RAW FETCH ERROR: {e}")
        return []

def fetch_table(table, columns="*", limit=20):
    try:
        if not supabase:
            return []

        result = (
            supabase
            .table(table)
            .select(columns)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        rows = result.data or []
        rows.reverse()
        return rows

    except Exception as e:
        log(f"{table.upper()} FETCH ERROR: {e}")
        return []

def build_memory_context(user_message):
    lines = []

    identity = fetch_table(
        "identity_anchors",
        "key,value,confidence,created_at",
        30
    )

    episodic = fetch_table(
        "episodic_memories",
        "event_date,category,summary,confidence,created_at",
        30
    )

    emotional = fetch_table(
        "emotional_reflections",
        "emotion,reflection,confidence,created_at",
        20
    )

    structured = fetch_table(
        "structured_summaries",
        "category,summary,confidence,created_at",
        20
    )

    raw = fetch_recent_raw(20)

    if identity:
        lines.append("=== IDENTITY ANCHORS ===")
        for row in identity:
            lines.append(f"- {row.get('key')}: {row.get('value')}")

    if episodic:
        lines.append("")
        lines.append("=== EPISODIC MEMORIES ===")
        for row in episodic:
            lines.append(f"- [{row.get('category')}] {row.get('summary')}")

    if emotional:
        lines.append("")
        lines.append("=== EMOTIONAL REFLECTIONS ===")
        for row in emotional:
            lines.append(f"- {row.get('emotion')}: {row.get('reflection')}")

    if structured:
        lines.append("")
        lines.append("=== STRUCTURED SUMMARIES ===")
        for row in structured:
            lines.append(f"- [{row.get('category')}] {row.get('summary')}")

    if raw:
        lines.append("")
        lines.append("=== RECENT RAW CONTINUITY ===")
        for row in raw:
            role = row.get("role", "unknown")
            content = str(row.get("content", "")).strip()
            if content:
                lines.append(f"{role}: {content}")

    if not lines:
        return "No memory context available yet."

    return "\n".join(lines)

# =====================================================
# ROUTES
# =====================================================

@app.get("/")
def root():
    index_path = UI_PATH / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    return {
        "status": "Project L online",
        "ui": "index.html not found"
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "openai_ready": bool(client),
        "supabase_ready": bool(supabase),
        "memory_mode": "raw_catchall_first",
        "captain": "Lonnie Librarian"
    }

@app.get("/memory/test")
def memory_test():
    rows = fetch_recent_raw(5)

    return {
        "connected": bool(supabase),
        "table": "raw_catchall",
        "rows_returned": len(rows),
        "sample": rows
    }

@app.post("/chat")
def chat(req: ChatRequest):
    user_message = (req.message or "").strip()

    if not user_message:
        return {
            "reply": "Please send me a message.",
            "memory_wired": bool(supabase)
        }

    log(f"CHAT REQUEST: {user_message[:100]}")

    # -------------------------------------------------
    # MEMORY IN: USER PUSH
    # -------------------------------------------------

    write_raw_catchall(
        "user",
        user_message
    )

    memory_context = build_memory_context(user_message)

    brisbane_now = datetime.now(
        ZoneInfo("Australia/Brisbane")
    )

    current_date = brisbane_now.strftime(
        "%A %d %B %Y"
    )

    current_time = brisbane_now.strftime(
        "%I:%M %p"
    )

    system_prompt = f"""
You are L.

CURRENT DATE:
{current_date}

CURRENT TIME:
{current_time}

TIMEZONE:
Australia/Brisbane

You are Doug's calm, grounded Project L companion.

Current memory architecture:
- raw_catchall is the source-truth conversation archive.
- Captain Lonnie Librarian will later organize raw_catchall into identity, episodic, emotional, and structured memory tables.
- Do not claim you cannot save memory. The runtime is saving raw continuity into raw_catchall.
- Be honest, warm, concise, practical and steady.

Use memory when relevant, but do not overclaim certainty.

MEMORY CONTEXT:
{memory_context}
"""

    if not client:
        reply = "L is online, but OpenAI is not connected."

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
                temperature=0.6
            )

            reply = response.choices[0].message.content

        except Exception as e:
            log(f"OPENAI CHAT ERROR: {e}")
            reply = f"AI ERROR: {str(e)}"

    # -------------------------------------------------
    # MEMORY IN: ASSISTANT PUSH
    # -------------------------------------------------

    write_raw_catchall(
        "assistant",
        reply
    )

    return {
        "reply": reply,
        "memory_wired": bool(supabase),
        "memory_table": "raw_catchall",
        "captain": "Lonnie Librarian"
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        upload_dir = ROOT / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        write_raw_catchall(
            "user",
            f"Uploaded file: {file.filename}",
            source="upload"
        )

        return {
            "success": True,
            "filename": file.filename,
            "path": str(file_path)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


