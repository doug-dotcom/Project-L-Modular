import os
import sys
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

from core.memory_retriever import retrieve_memory_context
from memory.sync.engine import run_sync



from memory.retrieval.short_term_retrieval import (
    build_short_term_packet
)

from agents.captain_ellie.captain_ellie import (
    build_runtime_context
)

from memory.classifier.short_term_classifier import (
    classify_message
)


from agents.brittany_browser.brittany import (
    should_handle,
    investigate
)

# =====================================================
# ENV
# =====================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# =====================================================
# LOGGER
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

    client = OpenAI(
        api_key=OPENAI_API_KEY
    )

    log("OPENAI CLIENT INITIALIZED")

# =====================================================
# SUPABASE
# =====================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase = None

if SUPABASE_URL and SUPABASE_KEY:

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    log("SUPABASE CONNECTED")

# =====================================================
# FASTAPI
# =====================================================

app = FastAPI(
    title="Project L",
    version="memory-retrieval-1.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# UI
# =====================================================

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
# RAW MEMORY WRITER
# =====================================================

def write_raw_catchall(
    role,
    content,
    source="chat"
):

    try:

        if not supabase:

            log("SUPABASE NOT CONNECTED")

            return False

        payload = {
            "role": str(role),
            "source": str(source),
            "content": str(content),
            "metadata": {}
        }

        supabase.table(
            "raw_catchall"
        ).insert(
            payload
        ).execute()

        log(f"RAW MEMORY SAVED: {role}")

        return True

    except Exception as e:

        import traceback

        log(f"RAW MEMORY ERROR: {e}")

        log(traceback.format_exc())

        return False


# =====================================================
# SHORT-TERM MEMORY WRITER
# =====================================================

def write_short_term_memory(
    table_name,
    role,
    content
):

    try:

        if not supabase:
            return False

        payload = {
            "role": str(role),
            "content": str(content)
        }

        supabase.table(
            table_name
        ).insert(
            payload
        ).execute()

        log(
            f"SHORT-TERM MEMORY SAVED -> {table_name}"
        )

        # ---------------------------------------------
        # ENFORCE MEMORY LIMIT
        # ---------------------------------------------

        enforce_short_term_limit(
            table_name
        )

        return True

    except Exception as e:

        log(
            f"SHORT-TERM MEMORY ERROR: {e}"
        )

        return False


# =====================================================
# SHORT-TERM MEMORY LIMIT ENFORCER
# =====================================================

def enforce_short_term_limit(
    table_name,
    limit_count=1000
):

    try:

        if not supabase:
            return

        result = supabase.table(
            table_name
        ).select(
            "id"
        ).order(
            "id",
            desc=False
        ).execute()

        rows = result.data or []

        if len(rows) <= limit_count:
            return

        overflow = len(rows) - limit_count

        ids_to_delete = [
            row["id"]
            for row in rows[:overflow]
        ]

        supabase.table(
            table_name
        ).delete().in_(
            "id",
            ids_to_delete
        ).execute()

        log(
            f"SHORT-TERM CLEANUP -> {table_name} | REMOVED: {overflow}"
        )

    except Exception as e:

        log(
            f"SHORT-TERM CLEANUP ERROR: {e}"
        )

# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():

    index_path = UI_PATH / "index.html"

    if index_path.exists():

        return FileResponse(index_path)

    return {
        "status": "Project L online"
    }

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "openai_ready": bool(client),
        "supabase_ready": bool(supabase),
        "memory_retrieval": True,
        "brittany_ready": True
    }

# =====================================================
# MEMORY TEST
# =====================================================

@app.get("/memory/test")
def memory_test():

    try:

        result = retrieve_memory_context(
            "Tell me about Doug",
            limit=8
        )

        return {
            "success": True,
            "domains": result.get("domains", []),
            "memory_count": len(result.get("memories", [])),
            "context_preview": result.get("context", "")[:1000]
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

# =====================================================
# CHAT
# =====================================================

@app.post("/chat")
def chat(req: ChatRequest):

    user_message = (req.message or "").strip()

    if not user_message:

        return {
            "reply": "Please send me a message."
        }

    log(f"CHAT REQUEST: {user_message[:100]}")

    # -------------------------------------------------
    # SAVE USER MEMORY
    # -------------------------------------------------

    write_raw_catchall(
        "user",
        user_message
    )

        # -------------------------------------------------
    # SHORT-TERM RETRIEVAL ONLY
    # -------------------------------------------------

    retrieved_rows = []

    short_term_context = ""

    try:

        recent = supabase.table(
            short_term_domain
        ).select(
            "*"
        ).order(
            "id",
            desc=True
        ).limit(
            20
        ).execute()

        retrieved_rows = recent.data or []

        retrieved_rows.reverse()

        short_term_context = build_short_term_packet(
            retrieved_rows
        )

        log(
            f"SHORT-TERM RETRIEVAL COUNT: {len(retrieved_rows)}"
        )

    except Exception as e:

        log(
            f"SHORT-TERM RETRIEVAL ERROR: {e}"
        )

    domains = [short_term_domain]

    memory_context = short_term_context

    # -------------------------------------------------
    # TIME
    # -------------------------------------------------

    brisbane_now = datetime.now(
        ZoneInfo("Australia/Brisbane")
    )

    current_date = brisbane_now.strftime(
        "%A %d %B %Y"
    )

    current_time = brisbane_now.strftime(
        "%I:%M %p"
    )

    # -------------------------------------------------
    # SYSTEM PROMPT
    # -------------------------------------------------

    system_prompt = f"""
You are L.

CURRENT DATE:
{current_date}

CURRENT TIME:
{current_time}

TIMEZONE:
Australia/Brisbane

You are Doug's calm, grounded Project L companion.

Use memory naturally and accurately.

MEMORY DOMAINS:
{domains}

CAPTAIN ELLIE RUNTIME CONTEXT:
{runtime_context_packet}

MEMORY CONTEXT:
{memory_context}
"""

    # -------------------------------------------------
    # BRITTANY ROUTING
    # -------------------------------------------------

    if should_handle(user_message):

        log("ROUTING TO BRITTANY")

        try:

            reply = investigate(user_message)

        except Exception as e:

            log(f"BRITTANY ERROR: {e}")

            reply = f"BRITTANY ERROR: {str(e)}"

    else:

        # -------------------------------------------------
        # OPENAI
        # -------------------------------------------------

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
    # SAVE ASSISTANT MEMORY
    # -------------------------------------------------

    write_raw_catchall(
        "assistant",
        reply
    )

        # -------------------------------------------------
    # SHORT-TERM MEMORY MODE
    # -------------------------------------------------

    log(
        "SHORT-TERM MEMORY MODE ACTIVE"
    )

    # -------------------------------------------------
    # RETURN
    # -------------------------------------------------

    return {
        "reply": reply,
        "domains": domains,
        "memory_wired": bool(supabase),
        "memory_count": len(
            retrieved.get("memories", [])
        ),
        "brittany_enabled": True
    }

# =====================================================
# FILE UPLOAD
# =====================================================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...)
):

    try:

        upload_dir = ROOT / "uploads"

        upload_dir.mkdir(
            parents=True,
            exist_ok=True
        )

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



