# =====================================================
# IMPORTS
# =====================================================

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

# =====================================================
# MEMORY + CONTEXT IMPORTS
# =====================================================

from memory.retrieval.short_term_retrieval import (
    build_short_term_packet
)

from core.memory_retriever import (
    retrieve_memory_context
)

from memory.classifier.short_term_classifier import (
    classify_message
)

# =====================================================
# AGENT IMPORTS
# =====================================================

from agents.captain_ellie.captain_ellie import (
    build_runtime_context
)

from agents.tegan.tegan import (
    route_message
)

# =====================================================
# ENVIRONMENT
# =====================================================

try:

    from dotenv import load_dotenv

    load_dotenv()

except Exception:

    pass

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT)
    )

# =====================================================
# LOGGER
# =====================================================

def log(msg):

    print(
        f"{datetime.now().isoformat()} | {msg}"
    )

# =====================================================
# IDENTITY
# =====================================================

IDENTITY_FILE = (
    ROOT
    / "memory"
    / "identity_core"
    / "l_identity.json"
)

def load_identity_core():

    try:

        with open(
            IDENTITY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        log(
            f"L IDENTITY LOAD ERROR: {e}"
        )

        return {}

def build_identity_context():

    identity_data = load_identity_core()

    return f"""
L Identity Core

Core Philosophy:
{identity_data.get("core_philosophy", "")}

Communication Style:
{identity_data.get("communication_style", [])}

Identity Anchors:
{identity_data.get("identity_anchors", [])}

Purpose:
{identity_data.get("purpose", [])}
"""

# =====================================================
# OPENAI
# =====================================================

MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

client = None

if OPENAI_API_KEY:

    client = OpenAI(
        api_key=OPENAI_API_KEY
    )

    log(
        "OPENAI CLIENT INITIALIZED"
    )

# =====================================================
# SUPABASE
# =====================================================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    ""
)

SUPABASE_KEY = (
    os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        ""
    )
    or
    os.getenv(
        "SUPABASE_KEY",
        ""
    )
)

supabase = None

if SUPABASE_URL and SUPABASE_KEY:

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    log(
        "SUPABASE CONNECTED"
    )

# =====================================================
# FASTAPI
# =====================================================

app = FastAPI(
    title="Project L",
    version="persistent-cognition-3.1"
)

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)

# =====================================================
# UI
# =====================================================

UI_PATH = ROOT / "ui"

if UI_PATH.exists():

    app.mount(

        "/ui",

        StaticFiles(
            directory=UI_PATH
        ),

        name="ui"

    )

# =====================================================
# MODELS
# =====================================================

class ChatRequest(BaseModel):

    message: str

# =====================================================
# RAW MEMORY
# =====================================================

def write_raw_catchall(
    role,
    content,
    source="chat"
):

    try:

        if not supabase:

            log(
                "SUPABASE NOT CONNECTED"
            )

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

        log(
            f"RAW MEMORY SAVED: {role}"
        )

        return True

    except Exception as e:

        log(
            f"RAW MEMORY ERROR: {e}"
        )

        return False

# =====================================================
# SHORT TERM MEMORY
# =====================================================

def enforce_short_term_limit(
    table_name,
    limit_count=1000
):

    try:

        if not supabase:

            return

        result = (
            supabase.table(
                table_name
            )
            .select("id")
            .order(
                "id",
                desc=False
            )
            .execute()
        )

        rows = result.data or []

        if len(rows) <= limit_count:

            return

        overflow = (
            len(rows)
            - limit_count
        )

        ids_to_delete = [

            row["id"]

            for row in rows[:overflow]

        ]

        (
            supabase.table(
                table_name
            )
            .delete()
            .in_(
                "id",
                ids_to_delete
            )
            .execute()
        )

        log(
            f"SHORT TERM CLEANUP -> "
            f"{table_name} | "
            f"REMOVED: {overflow}"
        )

    except Exception as e:

        log(
            f"SHORT TERM CLEANUP ERROR: {e}"
        )

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

        enforce_short_term_limit(
            table_name
        )

        log(
            f"SHORT TERM MEMORY SAVED -> "
            f"{table_name}"
        )

        return True

    except Exception as e:

        log(
            f"SHORT TERM MEMORY ERROR: {e}"
        )

        return False

# =====================================================
# CONTINUITY
# =====================================================

def build_conversation_continuity(
    limit_count=5
):

    try:

        if not supabase:

            return ""

        result = (
            supabase.table(
                "raw_catchall"
            )
            .select("*")
            .order(
                "id",
                desc=True
            )
            .limit(
                limit_count
            )
            .execute()
        )

        rows = result.data or []

        rows.reverse()

        continuity = []

        for row in rows:

            role = row.get(
                "role",
                "unknown"
            )

            content = str(
                row.get(
                    "content",
                    ""
                )
            ).strip()

            if not content:

                continue

            continuity.append(
                f"{role.upper()}: {content}"
            )

        return "\n".join(
            continuity
        )

    except Exception as e:

        log(
            f"CONTINUITY ERROR: {e}"
        )

        return ""

# =====================================================
# TIME CONTEXT
# =====================================================

def build_time_context():

    brisbane_now = datetime.now(
        ZoneInfo(
            "Australia/Brisbane"
        )
    )

    return {

        "date":
            brisbane_now.strftime(
                "%A %d %B %Y"
            ),

        "time":
            brisbane_now.strftime(
                "%I:%M %p"
            ),

        "timezone":
            "Australia/Brisbane"

    }

# =====================================================
# FILE TYPES
# =====================================================

def detect_file_type(
    filename
):

    lower = filename.lower()

    if lower.endswith(".csv"):

        return "csv"

    if lower.endswith(".pdf"):

        return "pdf"

    if lower.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp"
        )
    ):

        return "images"

    if lower.endswith(
        (
            ".doc",
            ".docx",
            ".txt",
            ".rtf"
        )
    ):

        return "docs"

    return "archive"

# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():

    index_path = (
        UI_PATH
        / "index.html"
    )

    if index_path.exists():

        return FileResponse(
            index_path
        )

    return {
        "status":
            "Project L online"
    }

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
def health():

    return {

        "status": "ok",

        "openai_ready":
            bool(client),

        "supabase_ready":
            bool(supabase),

        "persistent_identity":
            True,

        "long_term_memory":
            True,

        "captain_ellie":
            True,

        "tegan_orchestrator":
            True,

        "continuity_loop":
            True,

        "unified_interface":
            True

    }

# =====================================================
# CHAT
# =====================================================

@app.post("/chat")
def chat(
    req: ChatRequest
):

    user_message = (
        req.message or ""
    ).strip()

    if not user_message:

        return {

            "reply":
                "Please send me a message."

        }

    log(
        f"CHAT REQUEST: "
        f"{user_message[:100]}"
    )

    log(
        "TEGAN ACTIVE"
    )

    # =================================================
    # DEFAULTS
    # =================================================

    short_term_domain = (
        "short_term_general"
    )

    domains = [
        short_term_domain
    ]

    retrieved_rows = []

    short_term_context = ""

    long_term_context = ""

    runtime_context_packet = ""

    continuity_context = (
        build_conversation_continuity()
    )

    # =================================================
    # DOMAIN CLASSIFICATION
    # =================================================

    try:

        short_term_domain = (
            classify_message(
                user_message
            )
        )

        domains = [
            short_term_domain
        ]

        log(
            f"SHORT TERM DOMAIN: "
            f"{short_term_domain}"
        )

    except Exception as e:

        log(
            f"CLASSIFICATION ERROR: {e}"
        )

    # =================================================
    # SAVE USER MEMORY
    # =================================================

    write_short_term_memory(

        short_term_domain,

        "user",

        user_message

    )

    write_raw_catchall(

        "user",

        user_message

    )

    # =================================================
    # MEMORY RETRIEVAL
    # =================================================

    try:

        if supabase:

            recent = (
                supabase.table(
                    short_term_domain
                )
                .select("*")
                .order(
                    "id",
                    desc=True
                )
                .limit(20)
                .execute()
            )

            retrieved_rows = (
                recent.data or []
            )

            retrieved_rows.reverse()

            short_term_context = (
                build_short_term_packet(
                    retrieved_rows
                )
            )

            long_term_context = (
                retrieve_memory_context(
                    user_message
                )
            )

            log(
                f"SHORT TERM RETRIEVAL COUNT: "
                f"{len(retrieved_rows)}"
            )

    except Exception as e:

        log(
            f"SHORT TERM RETRIEVAL ERROR: {e}"
        )

    # =================================================
    # CAPTAIN ELLIE
    # =================================================

    try:

        runtime_context_packet = (
            build_runtime_context(
                short_term_context,
                short_term_domain
            )
        )

    except Exception as e:

        log(
            f"ELLIE CONTEXT ERROR: {e}"
        )

    # =================================================
    # CONTEXT BUILD
    # =================================================

    time_context = (
        build_time_context()
    )

    identity_context = (
        build_identity_context()
    )

    # =================================================
    # SYSTEM PROMPT
    # =================================================

    system_prompt = f"""
You are L.

CURRENT DATE:
{time_context["date"]}

CURRENT TIME:
{time_context["time"]}

TIMEZONE:
{time_context["timezone"]}

You are Doug's calm grounded companion.

Use memory naturally and accurately.

You are the only voice Doug talks to.

Internal agents such as Fiona, Emily, Callie, Tanya, Brittany, and Tegan are hidden cognition modules.

Never speak as those agents.

Never tell Doug to talk to those agents.

Consult them internally if routing selects them, then answer as L.

ACTIVE DOMAIN:
{domains}

L IDENTITY CORE:
{identity_context}

CAPTAIN ELLIE RUNTIME CONTEXT:
{runtime_context_packet}

SHORT TERM MEMORY CONTEXT:
{short_term_context}

LONG TERM MEMORY CONTEXT:
{long_term_context}

ACTIVE CONVERSATION CONTINUITY:
{continuity_context}

CONTINUITY RULES:
- Maintain active conversational topics naturally.
- Track implied meaning.
- Track unresolved references.
- Do not treat every message as isolated.
- Keep emotional and topic continuity.
- Join the dots, no more no less.
"""

    # =================================================
    # TEGAN ORCHESTRATION
    # =================================================

    agent_result = (
        route_message(
            user_message
        )
    )

    active_agent = (
        agent_result.get(
            "agent",
            "L Core"
        )
    )

    if agent_result.get(
        "handled"
    ):

        log(
            f"INTERNAL ORCHESTRATION: "
            f"{active_agent}"
        )

        reply = (
            agent_result.get(
                "reply",
                ""
            )
        )

    else:

        if not client:

            reply = (
                "L is online but "
                "OpenAI is not connected."
            )

        else:

            try:

                response = (
                    client.chat.completions.create(

                        model=MODEL,

                        messages=[

                            {
                                "role": "system",
                                "content":
                                    system_prompt
                            },

                            {
                                "role": "user",
                                "content":
                                    user_message
                            }

                        ],

                        temperature=0.6

                    )
                )

                reply = (
                    response
                    .choices[0]
                    .message
                    .content
                )

            except Exception as e:

                log(
                    f"OPENAI CHAT ERROR: {e}"
                )

                reply = (
                    f"AI ERROR: {str(e)}"
                )

    # =================================================
    # SAVE ASSISTANT MEMORY
    # =================================================

    write_short_term_memory(

        short_term_domain,

        "assistant",

        reply

    )

    write_raw_catchall(

        "assistant",

        reply

    )

    # =================================================
    # RETURN
    # =================================================

    return {

        "reply":
            reply,

        "domains":
            domains,

        "short_term_domain":
            short_term_domain,

        "memory_count":
            len(retrieved_rows),

        "short_term_memory":
            True,

        "long_term_memory":
            True,

        "persistent_identity":
            True,

        "captain_ellie":
            True,

        "tegan_orchestrator":
            True,

        "continuity_loop":
            True,

        "active_agent":
            "L"

    }

# =====================================================
# FILE UPLOAD
# =====================================================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...)
):

    try:

        filename = (
            file.filename
        )

        file_type = (
            detect_file_type(
                filename
            )
        )

        upload_dir = (
            ROOT
            / "uploads"
            / file_type
        )

        upload_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        file_path = (
            upload_dir
            / filename
        )

        content = (
            await file.read()
        )

        with open(
            file_path,
            "wb"
        ) as f:

            f.write(content)

        storage_path = (
            f"{file_type}/{filename}"
        )

        uploaded_to_storage = False

        storage_error = None

        if supabase:

            try:

                supabase.storage.from_(
                    "uploads"
                ).upload(

                    storage_path,

                    content,

                    {
                        "content-type":
                            file.content_type
                            or
                            "application/octet-stream",

                        "upsert":
                            "true"
                    }

                )

                uploaded_to_storage = True

                log(
                    f"SUPABASE STORAGE OK: "
                    f"{storage_path}"
                )

            except Exception as e:

                storage_error = str(e)

                log(
                    f"SUPABASE STORAGE ERROR: "
                    f"{storage_error}"
                )

        artifact_metadata = {

            "event":
                "file_upload",

            "filename":
                filename,

            "file_type":
                file_type,

            "local_path":
                str(file_path),

            "storage_bucket":
                "uploads",

            "storage_path":
                storage_path,

            "uploaded_to_storage":
                uploaded_to_storage,

            "storage_error":
                storage_error

        }

        write_raw_catchall(

            "user",

            json.dumps(
                artifact_metadata
            ),

            source="upload"

        )

        return {

            "success":
                True,

            "filename":
                filename,

            "file_type":
                file_type,

            "local_path":
                str(file_path),

            "storage_bucket":
                "uploads",

            "storage_path":
                storage_path,

            "uploaded_to_storage":
                uploaded_to_storage,

            "storage_error":
                storage_error

        }

    except Exception as e:

        log(
            f"UPLOAD ERROR: {e}"
        )

        return {

            "success":
                False,

            "error":
                str(e)

        }