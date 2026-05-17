




# =====================================================
# JSON IDENTITY CONTEXT
# =====================================================

def load_identity_context():

    try:

        identity_path = (
            ROOT
            / "memory"
            / "identity.json"
        )

        if not identity_path.exists():
            return ""

        data = json.loads(
            identity_path.read_text(
                encoding="utf-8"
            )
        )

        lines = []

        identity = data.get(
            "identity",
            {}
        )

        family = data.get(
            "family",
            {}
        )

        projects = data.get(
            "projects",
            {}
        )

        sport = data.get(
            "sport",
            {}
        )

        if identity.get("name"):

            lines.append(
                f"Name: {identity.get('name')}"
            )

        values = identity.get(
            "core_values",
            []
        )

        if values:

            lines.append(
                "Core Values: "
                + ", ".join(values)
            )

        children = family.get(
            "children",
            []
        )

        if children:

            lines.append(
                "Children: "
                + ", ".join(children)
            )

        project_list = projects.get(
            "primary",
            []
        )

        if project_list:

            lines.append(
                "Projects: "
                + ", ".join(project_list)
            )

        sports = sport.get(
            "primary",
            []
        )

        if sports:

            lines.append(
                "Sports: "
                + ", ".join(sports)
            )

        return "\n".join(lines)

    except Exception as e:

        log_exception(
            f"IDENTITY LOAD FAILED: {e}"
        )

        return ""



# =====================================================
# LONG TERM MEMORY STORAGE
# =====================================================

def store_long_term_memory(
    category,
    content,
    importance=5
):

    if not supabase:
        return False

    try:

        payload = {
            "category": str(category),
            "content": str(content),
            "importance": int(importance)
        }

        supabase.table(
            "memories"
        ).insert(
            payload
        ).execute()

        return True

    except Exception as e:

        log_exception(
            f"MEMORY STORE FAILED: {e}"
        )

        return False


# =====================================================
# MEMORY IMPORTANCE DETECTION
# =====================================================

def detect_memory_importance(
    text
):

    text_lower = str(text).lower()

    high_priority = [
        "my children",
        "my family",
        "project l",
        "important",
        "remember this",
        "please save",
        "my name is",
        "i have",
        "i am"
    ]

    for trigger in high_priority:

        if trigger in text_lower:
            return 9

    return 3



# =========================================================
# SUPABASE MEMORY CONTEXT
# =========================================================

def build_supabase_memory_context(
    query,
    limit=10
):

    if not supabase:
        return ""

    try:

        result = (
            supabase
            .table("memories")
            .select("*")
            .limit(limit)
            .execute()
        )

        rows = result.data

        context_lines = []

        for row in rows:

            try:

                category = str(
                    row.get(
                        "category",
                        "memory"
                    )
                ).strip()

                content = str(
                    row.get(
                        "content",
                        ""
                    )
                ).strip()

                if not content:
                    continue

                line = (
                    f"[{category}] {content}"
                )

                context_lines.append(line)

            except Exception as e:

                print(
                    "SUPABASE MEMORY ROW ERROR:",
                    e
                )

        return "\n".join(context_lines)

    except Exception as e:

        print(
            "SUPABASE MEMORY ERROR:",
            e
        )

        return ""


from openai import OpenAI

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client

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
# MEMORY OBSERVABILITY
# =====================================================

OBS_PATH = (
    ROOT
    / "memory"
    / "observability"
    / "runtime_events.json"
)

def log_runtime_event(event):

    try:

        import json
        from datetime import datetime

        events = []

        if OBS_PATH.exists():

            try:

                events = json.loads(
                    OBS_PATH.read_text(
                        encoding="utf-8"
                    )
                )

            except:
                events = []

        event["timestamp"] = str(
            datetime.now()
        )

        events.append(event)

        events = events[-100:]

        OBS_PATH.write_text(
            json.dumps(
                events,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    except Exception as e:

        log_exception(
            f"OBSERVABILITY ERROR: {e}"
        )





# =====================================================
# MEMORY ENGINE
# =====================================================

from core.memory_engine import (
    save_memory,
    memory_stats
)

from memory.local_runtime import (
    process,
    build_context
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

except Exception as e:

    log_exception(f"OPENAI INIT FAILED: {e}")

# =====================================================
# SUPABASE
# =====================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase = None

try:

    if SUPABASE_URL and SUPABASE_KEY:

        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

        log_info("SUPABASE CONNECTED")

except Exception as e:

    log_exception(f"SUPABASE FAILED: {e}")

# =====================================================
# MEMORY RETRIEVAL
# =====================================================

def fetch_relevant_memories(user_message, limit=5):

    if not supabase:
        return []

    try:

        result = (
            supabase
            .table("memories")
            .select("category, content")
            .ilike("content", f"%{user_message}%")
            .limit(limit)
            .execute()
        )

        if result.data:
            return result.data

        words = user_message.lower().split()

        for word in words:

            result = (
                supabase
                .table("memories")
                .select("category, content")
                .ilike("category", f"%{word}%")
                .limit(limit)
                .execute()
            )

            if result.data:
                return result.data

        return []

    except Exception as e:

        log_exception(f"MEMORY FETCH FAILED: {e}")

        return []

# =====================================================
# MEMORY FORMATTER
# =====================================================

def format_memory_context(memories):

    if not memories:
        return "No relevant long-term memories found."

    lines = []

    for mem in memories:

        content = mem.get("content", "")
        category = mem.get("category", "general")

        lines.append(
            f"- ({category}) {content}"
        )

    return "\n".join(lines)

# =====================================================
# SERVER START
# =====================================================

log_info("PROJECT L SERVER STARTING")

# =====================================================
# RUNTIME STACK
# =====================================================

runtime_stack = build_runtime_stack()

# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="Project L",
    version="1.0.0"
)

app.state.runtime_stack = runtime_stack

# =====================================================
# ROUTERS
# =====================================================

app.include_router(runtime_router)

# =====================================================
# UI
# =====================================================

UI_PATH = ROOT / "ui"

app.mount("/ui", StaticFiles(directory=UI_PATH), name="ui")

# =====================================================
# CORS
# =====================================================

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

    return FileResponse(UI_PATH / "index.html")

# =====================================================
# HEALTH
# =====================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "openai_ready": bool(client),
        "memory_stats": memory_stats()
    }

# =====================================================
# CHAT
# =====================================================

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

    process(user_message)

    runtime_continuity = (
        build_context()
    )

    identity_context = (
        load_identity_context()
    )

    importance = detect_memory_importance(
        user_message
    )

    if importance >= 8:

        store_long_term_memory(
            category="conversation",
            content=user_message,
            importance=importance
        )

    runtime_package = (
        build_memory_runtime_package(
            user_message
        )
    )

    log_runtime_event({

        "user_message": user_message,

        "retrieval_count": len(
            runtime_package.get(
                "retrieval_results",
                []
            )
        ),

        "confidence": runtime_package.get(
            "confidence",
            {}
        ),

        "status": runtime_package.get(
            "status",
            {}
        )
    })

    relevant_memories = (
        runtime_package.get(
            "retrieval_results",
            []
        )
    )

    memory_context = (
        runtime_package.get(
            "context",
            ""
        )
    )

    confidence_layer = (
        runtime_package.get(
            "confidence_layer",
            ""
        )
    )

    system_prompt = f"""
You are L.

You are grounded, calm, practical and supportive.

Use memory naturally when relevant.

CONFIDENCE RULES:

- Only state information strongly if memory confidence is high.
- If memory is partial, summarise carefully.
- Do not invent timelines, emotions, relationships or assumptions.
- Prefer grounded synthesis over confident guessing.
- If uncertain, say you are uncertain.
- Prioritise continuity, accuracy and honesty.

MEMORY:
{memory_context}

CONFIDENCE:
{confidence_layer}

RUNTIME CONTINUITY:
{runtime_continuity}

IDENTITY CONTEXT:
{identity_context}
"""

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

    save_memory(
        "session",
        {
            "role": "assistant",
            "content": reply
        }
    )

    return {
        "reply": reply,
        "memory_wired": True,
        "retrieved_memories": relevant_memories,
        "confidence_layer": confidence_layer,
        "memory_stats": memory_stats()
    }

# =====================================================
# MEMORY TEST
# =====================================================

@app.get("/memory/test")
def memory_test():

    if not supabase:

        return {
            "connected": False
        }

    try:

        result = (
            supabase
            .table("memories")
            .select("*")
            .limit(3)
            .execute()
        )

        return {
            "connected": True,
            "rows": len(result.data),
            "sample": result.data
        }

    except Exception as e:

        return {
            "connected": False,
            "error": str(e)
        }









# =====================================================
# MEMORY OBSERVABILITY
# =====================================================

@app.get("/memory/observability")
def memory_observability():

    try:

        if not OBS_PATH.exists():

            return {
                "events": []
            }

        import json

        data = json.loads(
            OBS_PATH.read_text(
                encoding="utf-8"
            )
        )

        return {
            "events": data[-25:]
        }

    except Exception as e:

        return {
            "error": str(e)
        }




