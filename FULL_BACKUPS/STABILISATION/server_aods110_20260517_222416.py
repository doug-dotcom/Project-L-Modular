import json





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
# CONTINUITY_RUNTIME_SAFE
# =====================================================

CONTINUITY_DIR = (
    ROOT
    / "memory"
    / "continuity"
)

CONTINUITY_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CONTINUITY_FILE = (
    CONTINUITY_DIR
    / "continuity_state.json"
)

if not CONTINUITY_FILE.exists():

    CONTINUITY_FILE.write_text(
        json.dumps({
            "recent_topics": []
        }),
        encoding="utf-8"
    )


# =====================================================
# CONTINUITY SAFETY
# =====================================================

CONTINUITY_DIR = (
    ROOT
    / "memory"
    / "continuity"
)

CONTINUITY_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CONTINUITY_FILE = (
    CONTINUITY_DIR
    / "continuity_state.json"
)

if not CONTINUITY_FILE.exists():

    CONTINUITY_FILE.write_text(
        json.dumps({
            "recent_topics": []
        }),
        encoding="utf-8"
    )


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

from memory.domain_runtime import (
    build_domain_memory_context,
    cognition_runtime_status
)

from memory.memory_queue import (
    queue_memory_candidate
)

from memory.memory_classifier import (
    classify_pending_queue,
    classifier_status
)

from memory.memory_compression import (
    compress_pending_memories,
    compression_status
)

from memory.domain_updater import (
    safe_update_domains,
    domain_updater_status
)

from memory.memory_reinforcement import (
    reinforce_domains,
    reinforcement_status
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

def fetch_relevant_memories(user_message, limit=12):

    if not supabase:
        return []

    try:

        q = str(user_message or "").lower()

        semantic_map = {
            "family": [
                "family", "children", "kids", "child", "son", "daughter",
                "iyla", "ashton", "luella", "mehlia", "ages", "old", "grade"
            ],
            "insurance": [
                "tpd", "insurance", "zurich", "claim", "policy", "ime",
                "medical", "retired", "will"
            ],
            "sport": [
                "sport", "hockey", "field hockey", "fullback", "masters"
            ],
            "project": [
                "project l", "shine", "orchestration", "memory", "supabase",
                "runtime", "captains", "tegan", "dynamic modular"
            ],
            "identity": [
                "name", "doug", "values", "age", "single", "identity",
                "who am i", "about me"
            ]
        }

        search_terms = set()

        for word in q.replace("?", " ").replace(",", " ").split():
            if len(word) > 2:
                search_terms.add(word)

        for domain, terms in semantic_map.items():
            if domain in q or any(t in q for t in terms):
                search_terms.update(terms)
                search_terms.add(domain)

        rows_by_id = {}

        def add_rows(rows):
            for row in rows or []:
                rid = str(row.get("id", row.get("content", "")))
                if rid:
                    clean = {
                        "id": row.get("id"),
                        "type": row.get("type"),
                        "category": row.get("category", "memory"),
                        "content": row.get("content", ""),
                        "importance": row.get("importance", row.get("rank", 0)),
                        "metadata": row.get("metadata", {})
                    }
                    rows_by_id[rid] = clean

        # 1. Category match
        for term in list(search_terms)[:30]:
            try:
                result = (
                    supabase
                    .table("memories")
                    .select("id,type,category,content,importance,metadata")
                    .ilike("category", f"%{term}%")
                    .limit(limit)
                    .execute()
                )
                add_rows(result.data)
            except Exception:
                pass

        # 2. Content match
        for term in list(search_terms)[:30]:
            try:
                result = (
                    supabase
                    .table("memories")
                    .select("id,type,category,content,importance,metadata")
                    .ilike("content", f"%{term}%")
                    .limit(limit)
                    .execute()
                )
                add_rows(result.data)
            except Exception:
                pass

        rows = list(rows_by_id.values())

        def score(row):
            text = (
                str(row.get("category", "")) + " " +
                str(row.get("content", ""))
            ).lower()

            s = 0

            for term in search_terms:
                if term and term in text:
                    s += 3

            try:
                s += int(row.get("importance") or 0)
            except Exception:
                pass

            return s

        rows.sort(key=score, reverse=True)

        return rows[:limit]

    except Exception as e:

        log_exception(f"MEMORY FETCH FAILED: {e}")

        return []

# =====================================================
# MEMORY FORMATTER
# =====================================================

def format_memory_context(memories):

    if not memories:
        return "No relevant long-term memories found."

    grouped = {}

    for mem in memories:

        category = str(
            mem.get("category", "memory")
        ).strip()

        content = str(
            mem.get("content", "")
        ).strip()

        if not content:
            continue

        if category not in grouped:
            grouped[category] = []

        if content not in grouped[category]:
            grouped[category].append(content)

    lines = []

    for category, items in grouped.items():

        lines.append(f"[{category}]")

        for item in items[:8]:
            lines.append(f"- {item}")

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
        "domain_runtime": cognition_runtime_status(),

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

    queue_memory_candidate(
        user_message
    )

    if importance >= 8:

        store_long_term_memory(
            category="conversation",
            content=user_message,
            importance=importance
        )

    memory_context = (
        build_domain_memory_context(
            user_message
        )
    )

    log_runtime_event({

        "user_message": user_message,

        "domain_runtime": True,

        "memory_loaded": bool(
            memory_context
        ),

        "memory_length": len(
            memory_context
        )
    })

    relevant_memories = []

    confidence_layer = (
        "Structured cognition memory active."
    )

    system_prompt = f"""
You are L.

You are grounded, calm, practical and supportive.

Use cognition memory naturally when relevant.

IMPORTANT:
- The MEMORY section below is trusted structured cognition memory.
- Use it confidently when answering memory questions.
- Family, identity, work, sport and health memories are trusted continuity data.
- Do not ignore known cognition memories.
- Prioritise cognition memory over generic uncertainty.
- Group related memories together naturally.

CONFIDENCE RULES:

- Only state information strongly if memory confidence is high.
- If memory is partial, summarise carefully.
- Do not invent timelines, emotions, relationships or assumptions.
- Prefer grounded synthesis over confident guessing.
- If uncertain, say you are uncertain.
- Prioritise continuity, accuracy and honesty.

IMPORTANT:
- Identity memory is considered high-confidence continuity memory.
- Do NOT suppress identity continuity unless directly contradicted.
- Family, core values, projects and known identity anchors should be treated as persistent memory.

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

        "confidence_layer": confidence_layer,
        "domain_runtime": cognition_runtime_status(),

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



















