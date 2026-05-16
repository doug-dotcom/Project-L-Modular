from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from openai import OpenAI

from api.schemas import ChatRequest

from core.paths import (
    UPLOAD_DIR,
    LIFE_STORY_FILE,
    PROFILE_FILE,
    CONVERSATION_FILE,
    MEMORY_AUDIT_FILE,
    INVISIBLE_ORCHESTRA_LOG,
)


from core.json_store import (
    safe_load_json,
    safe_save_json,
)


from core.time_context import (
    build_time_context,
)

from core.config import (
    OPENAI_MODEL,
    ALLOWED_ORIGINS,
    TIMEZONE,
)

from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

import os
import json
import random


import shutil
import base64
import fitz

from memory.memory_engine import (
    build_context_weighting_layer,
    build_memory_confidence_context,
    build_natural_memory_injection,
    rank_relational_memories,
    extract_relational_memory,
    build_relational_memory_context,
    build_full_memory_audit,
    get_memory_record_count,
    process,
    build_context,
    detect_emotional_state,
    generate_emotional_tone,
)

load_dotenv()

print("USING CLEAN SHINE L SERVER V2")


# =========================================================
# GOOGLE CLOUD AUTH
# =========================================================
try:
    from api.google_auth import (
        build_auth_url,
        handle_callback,
        google_status,
        clear_credentials
    )

    GOOGLE_AUTH_AVAILABLE = True

except Exception as e:

    print("GOOGLE AUTH IMPORT ERROR:", e)

    GOOGLE_AUTH_AVAILABLE = False


# =========================================================
# PIXIE PICTURES AGENT
# =========================================================
try:

    from agents.pixie.pixie import (
        should_handle as pixie_should_handle
    )

    from agents.pixie.pixie import (
        create_image as pixie_create_image
    )

    PIXIE_AVAILABLE = True

except Exception as e:

    print("PIXIE IMPORT ERROR:", e)

    PIXIE_AVAILABLE = False

app = FastAPI()

# =====================================================
# STATIC IMAGE CORS FIX
# =====================================================

from fastapi.responses import Response

@app.middleware("http")
async def add_cors_headers(request, call_next):

    response = await call_next(request)

    response.headers["Access-Control-Allow-Origin"] = "*"

    response.headers["Access-Control-Allow-Methods"] = "*"

    response.headers["Access-Control-Allow-Headers"] = "*"

    return response

# app.add_middleware(HTTPSRedirectMiddleware)
client = OpenAI()

# =========================================================
# GENERATED IMAGE STATIC FILES
# =========================================================

os.makedirs(
    "generated_images",
    exist_ok=True
)

app.mount(
    "/generated_images",
    StaticFiles(directory="generated_images"),
    name="generated_images"
)














# =========================================================
# FIONA FINANCE AGENT
# =========================================================
try:

    from agents.fiona.fiona import (
        should_handle as fiona_should_handle
    )

    from agents.fiona.fiona import (
        handle_finance_request
    )

    FIONA_AVAILABLE = True

except Exception as e:

    print("FIONA IMPORT ERROR:", e)

    FIONA_AVAILABLE = False

# =========================================================
# WINNIE WHATSAPP AGENT
# =========================================================
try:

    from agents.winnie.winnie import (
        should_handle as winnie_should_handle
    )

    from agents.winnie.winnie import (
        handle_whatsapp_request
    )

    WINNIE_AVAILABLE = True

except Exception as e:

    print("WINNIE IMPORT ERROR:", e)

    WINNIE_AVAILABLE = False

# =========================================================
# TEGAN INTEGRATION SPINE AGENT
# =========================================================
try:

    from agents.tegan.tegan import (
        should_handle as tegan_should_handle
    )

    from agents.tegan.tegan import (
        handle_integration_request
    )

    TEGAN_AVAILABLE = True

except Exception as e:

    print("TEGAN IMPORT ERROR:", e)

    TEGAN_AVAILABLE = False

# =========================================================
# RICHIE REFLECTIVE LEARNING AGENT
# =========================================================
try:

    from agents.richie.richie import (
        should_handle as richie_should_handle
    )

    from agents.richie.richie import (
        handle_reflection_request
    )

    RICHIE_AVAILABLE = True

except Exception as e:

    print("RICHIE IMPORT ERROR:", e)

    RICHIE_AVAILABLE = False

# =========================================================
# NOELIE KNOWLEDGE RESEARCH AGENT
# =========================================================
try:

    from agents.noelie.noelie import (
        should_handle as noelie_should_handle
    )

    from agents.noelie.noelie import (
        handle_research_request
    )

    NOELIE_AVAILABLE = True

except Exception as e:

    print("NOELIE IMPORT ERROR:", e)

    NOELIE_AVAILABLE = False

# =========================================================
# GRACIE LEGACY BUILDER AGENT
# =========================================================
try:

    from agents.gracie.gracie import (
        should_handle as gracie_should_handle
    )

    from agents.gracie.gracie import (
        handle_legacy_request
    )

    GRACIE_AVAILABLE = True

except Exception as e:

    print("GRACIE IMPORT ERROR:", e)

    GRACIE_AVAILABLE = False

# =========================================================
# ADDIE TASK EXECUTION AGENT
# =========================================================
try:

    from agents.addie.addie import (
        should_handle as addie_should_handle
    )

    from agents.addie.addie import (
        handle_task_request as addie_handle_task_request
    )

    ADDIE_AVAILABLE = True

except Exception as e:

    print("ADDIE IMPORT ERROR:", e)

    ADDIE_AVAILABLE = False

# =========================================================
# EMME EMOTIONAL SUPPORT AGENT
# =========================================================
try:

    from agents.emme.emme import (
        should_handle as emme_should_handle
    )

    from agents.emme.emme import (
        handle_emotional_request
    )

    EMME_AVAILABLE = True

except Exception as e:

    print("EMME IMPORT ERROR:", e)

    EMME_AVAILABLE = False

# =====================================================
# META ROUTING SUPPRESSION
# =====================================================

META_SUPPRESSION_TERMS = [

    "orchestration",
    "routing",
    "agent",
    "agents",
    "system design",
    "architecture",
    "memory audit",
    "memory observability",
    "trigger logic",
    "suppression logic",
    "weighted routing",
    "cognition",
    "hard fix",
    "soft fix",
    "backend",
    "frontend",
    "server.py",
    "routes",
    "engines",
    "api"

]

def suppress_agent_routing(message):

    text = message.lower()

    for term in META_SUPPRESSION_TERMS:

        if term in text:

            print("")
            print("🛑 META ROUTING SUPPRESSION ACTIVE")
            print("TERM:", term)

            return True

    return False



# =========================================================
# MILLIE MEMORY KEEPER AGENT
# =========================================================
try:

    from agents.millie.millie import (
        should_handle as millie_should_handle
    )

    from agents.millie.millie import (
        handle_memory_request
    )

    MILLIE_AVAILABLE = True

except Exception as e:

    print("MILLIE IMPORT ERROR:", e)

    MILLIE_AVAILABLE = False

# =========================================================
# SALLY SKILLS LIBRARIAN AGENT
# =========================================================
try:

    from agents.sally.sally import (
        should_handle as sally_should_handle
    )

    from agents.sally.sally import (
        handle_skill_request,
        build_skill_prompt_layer
    )

    SALLY_AVAILABLE = True

except Exception as e:

    print("SALLY IMPORT ERROR:", e)

    SALLY_AVAILABLE = False

    def build_skill_prompt_layer(message):
        return ""

# =========================================================
# TANIA TASK AGENT
# =========================================================
try:

    from agents.tania.tania import (
        should_handle as tania_should_handle
    )

    from agents.tania.tania import (
        handle_task_request
    )

    TANIA_AVAILABLE = True

except Exception as e:

    print("TANIA IMPORT ERROR:", e)

    TANIA_AVAILABLE = False

# =========================================================
# CALLIE CALENDAR AGENT
# =========================================================
try:

    from agents.callie.callie import (
        should_handle as callie_should_handle
    )

    from agents.callie.callie import (
        handle_calendar_request
    )

    CALLIE_AVAILABLE = True

except Exception as e:

    print("CALLIE IMPORT ERROR:", e)

    CALLIE_AVAILABLE = False

# =========================================================
# EMILY EMAIL AGENT
# =========================================================
try:

    from agents.emily.emily import (
        should_handle as emily_should_handle
    )

    from agents.emily.emily import (
        handle_email_request
    )

    EMILY_AVAILABLE = True

except Exception as e:

    print("EMILY IMPORT ERROR:", e)

    EMILY_AVAILABLE = False

# =========================================================
# BRITTANY BROWSER AGENT
# =========================================================
try:
    from agents.brittany_browser.brittany import should_handle as brittany_should_handle
    from agents.brittany_browser.brittany import investigate as brittany_investigate
    BRITTANY_AVAILABLE = True
except Exception as e:
    print("BRITTANY IMPORT ERROR:", e)
    BRITTANY_AVAILABLE = False


app.add_middleware(
    CORSMiddleware,

    allow_origins=ALLOWED_ORIGINS,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

    expose_headers=["*"]
)



os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("memory", exist_ok=True)





DRIFT_TRIGGERS = [
    "confused",
    "overwhelmed",
    "lost",
    "drifting",
    "too much",
    "slow down",
    "not making sense",
    "reset",
    "spiraling",
    "panic",
    "anxious",
]

GROUNDING_RESPONSE = """
Doug may be drifting or overwhelmed.

Slow down.
Reduce information density.
Use short sections.
Use calm pacing.
Use clear next steps.
Prioritize clarity, safety, orientation, and one next action.
"""

MEMORY_IMPORTANCE = {
    "kids": 10,
    "children": 10,
    "iyla": 10,
    "ashton": 10,
    "luella": 10,
    "mehlia": 10,
    "army": 9,
    "east timor": 10,
    "kapooka": 9,
    "deployment": 9,
    "recovery": 10,
    "na": 10,
    "aa": 10,
    "stepwork": 9,
    "shine": 10,
    "purpose": 9,
    "identity": 8,
    "trauma": 9,
    "family": 10,
    "clarity": 8,
}

SEMANTIC_LINKS = {
    "east timor": [
        "army",
        "kapooka",
        "transport",
        "military",
        "enlistment",
        "deployment",
        "reserve scheme",
        "timor",
    ],
    "army": [
        "kapooka",
        "east timor",
        "transport corps",
        "deployment",
        "reserve scheme",
        "military",
    ],
    "school": [
        "girls",
        "childhood",
        "grade",
        "growing up",
        "teenage",
        "adolescence",
    ],
    "recovery": [
        "na",
        "aa",
        "meetings",
        "addiction",
        "stepwork",
        "sobriety",
        "clean",
    ],
    "family": [
        "kids",
        "children",
        "mehlia",
        "luella",
        "iyla",
        "ashton",
    ],
}



# =====================================================
# ECOSYSTEM AGENT STOCKTAKE V1
# =====================================================

def build_ecosystem_agent_stocktake():

    return """
Shine ecosystem agent stocktake:

Core:
- L: Primary companion identity and base cognition.

Memory:
- Millie: Memory keeper and continuity support.
- Supabase Memory Spine: Persistent semantic memory storage and retrieval.

Emotion:
- Emme: Emotional regulation and nervous-system support.

Execution:
- Addie: Task planning and execution support.
- Tania: Task creation and action handling.

Calendar:
- Callie: Calendar review and scheduling support.

Email:
- Emily: Gmail reading, full-email summaries, inbox triage, and email cognition.

Legacy:
- Gracie: Legacy preservation, life story, and family memory workflows.

Research:
- Noelie: Knowledge research and investigation support.
- Brittany: Browser/research investigation support where available.

Reflection:
- Richie: Reflective learning, pattern recognition, and insight support.

Orchestration:
- Tegan: Integration spine and ecosystem coordination.
- Sally: Skills librarian and external skill activation support.

Important:
Sally should support L quietly unless directly called.
Skills should augment L, not replace L.
"""



        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print("JSON LOAD ERROR:", path, e)
        return fallback





def load_profile():
    return safe_load_json(PROFILE_FILE, {})


def calculate_memory_score(text):
    score = 0
    text_lower = text.lower()

    for key, value in MEMORY_IMPORTANCE.items():
        if key in text_lower:
            score += value

    return score


def detect_drift(user_text):
    text = user_text.lower()
    return any(trigger in text for trigger in DRIFT_TRIGGERS)


def detect_intent(user_text):
    text = user_text.lower()

    if (
        "full file" in text
        or "full document" in text
        or "read full" in text
        or "show full" in text
        or "word for word" in text
        or "read the full" in text
        or "full story" in text
    ):
        return "full_recall"

    if (
        "remember" in text
        or "recall" in text
        or "what do you know" in text
        or "tell me about" in text
        or "what matters" in text
    ):
        return "memory_recall"

    return "normal"


def expand_search_terms(query):
    query_lower = query.lower()
    terms = [query_lower]

    words = query_lower.replace("?", "").replace(".", "").split()
    terms.extend(words)

    for key, linked_terms in SEMANTIC_LINKS.items():
        if key in query_lower:
            terms.extend(linked_terms)

    return list(set([t.strip() for t in terms if t.strip()]))


def search_life_story(query):
    stories = safe_load_json(LIFE_STORY_FILE, [])

    if not isinstance(stories, list):
        return []

    search_terms = expand_search_terms(query)
    matches = []

    for item in stories:
        title = str(item.get("title", ""))
        preview = str(item.get("preview", ""))
        full_content = str(
            item.get("full_content", item.get("content", ""))
        )

        text_blob = f"{title} {preview} {full_content}".lower()

        score = 0

        for term in search_terms:
            if term in text_blob:
                score += 1

        score += int(item.get("score", 0))

        if score > 0:
            copy_item = dict(item)
            copy_item["_score"] = score
            matches.append(copy_item)

    matches.sort(key=lambda x: x.get("_score", 0), reverse=True)

    return matches[:5]


def save_to_life_story(title, content_text):
    stories = safe_load_json(LIFE_STORY_FILE, [])

    if not isinstance(stories, list):
        stories = []

    preview_text = content_text[:3000]
    memory_score = calculate_memory_score(content_text)

    entry = {
        "title": title,
        "preview": preview_text,
        "full_content": content_text,
        "score": memory_score,
    }

    stories.append(entry)
    safe_save_json(LIFE_STORY_FILE, stories)

    audit_memory_event(
        "save",
        LIFE_STORY_FILE,
        {
            "title": title,
            "characters": len(content_text),
            "score": memory_score
        }
    )



def save_conversation_turn(user_msg, assistant_reply):

    try:

        conversations = safe_load_json(
            CONVERSATION_FILE,
            []
        )

        entry = {

            "timestamp": str(datetime.now()),

            "user": user_msg,

            "assistant": assistant_reply

        }

        conversations.append(entry)

        safe_save_json(
            CONVERSATION_FILE,
            conversations
        )

        audit_memory_event(
            "conversation_save",
            CONVERSATION_FILE,
            {
                "user_chars": len(user_msg),
                "assistant_chars": len(assistant_reply)
            }
        )

    except Exception as e:

        print(
            "CONVERSATION SAVE ERROR:",
            e
        )


def build_profile_context():
    profile = load_profile()

    if not profile:
        return ""

    return "\n\nCANONICAL PROFILE MEMORY:\n" + json.dumps(
        profile,
        indent=2,
        ensure_ascii=False,
    )



def build_recent_conversation_context():

    try:

        conversations = safe_load_json(
            CONVERSATION_FILE,
            []
        )

        if not conversations:
            return ""

        recent = conversations[-10:]

        context = "\n\nRECENT CONVERSATIONS:\n"

        for convo in recent:

            context += (
                "\nUSER: "
                + convo.get("user","")
            )

            context += (
                "\nL: "
                + convo.get("assistant","")
            )

            context += "\n"

        return context

    except Exception as e:

        print(
            "CONVO CONTEXT ERROR:",
            e
        )

        return ""


def build_story_context(user_msg):
    matches = search_life_story(user_msg)

    if not matches:
        return ""

    story_context = "\n\nRELEVANT STORY MEMORY:\n"

    for item in matches:
        story_context += "\n--- STORY MEMORY ---\n"
        story_context += item.get("preview", "")

    return story_context



# =====================================================
# INVISIBLE ORCHESTRA HOTFIX HELPERS
# =====================================================

INVISIBLE_ORCHESTRA_MODE = True


VISIBLE_ORCHESTRA_TRIGGERS = [
    "ecosystem status",
    "show agents",
    "agent status",
    "which agent",
    "show orchestration",
    "debug agents",
    "diagnostic",
    "tegan show"
]


def wants_visible_orchestra(message: str) -> bool:

    text = message.lower()

    return any(
        trigger in text
        for trigger in VISIBLE_ORCHESTRA_TRIGGERS
    )


def log_orchestra_event(agent_name, user_msg, agent_reply):

    try:

        logs = safe_load_json(
            INVISIBLE_ORCHESTRA_LOG,
            []
        )

        logs.append(
            {
                "timestamp": str(datetime.now()),
                "agent": agent_name,
                "user": user_msg,
                "agent_reply": agent_reply
            }
        )

        safe_save_json(
            INVISIBLE_ORCHESTRA_LOG,
            logs
        )

    except Exception as e:

        print(
            "ORCHESTRA LOG ERROR:",
            e
        )


def strip_agent_headers(reply: str) -> str:

    if not reply:

        return ""

    text = reply.strip()

    headers = [
        "# 🧠 Millie Memory Keeper",
        "# ❤️ Emme Emotional Support",
        "# ✅ Addie Task Execution",
        "# 📖 Gracie Legacy Builder",
        "# 🌐 Noelie Knowledge Research",
        "# 🪞 Richie Reflective Learning",
        "# 🔗 Tegan Integration Spine",
        "# 💬 Winnie WhatsApp Cognition",
        "# 💰 Fiona Finance Cognition",
        "🧠 Millie Memory Keeper:",
        "❤️ Emme Emotional Support:",
        "✅ Addie Task Execution:",
        "📖 Gracie Legacy Builder:",
        "🌐 Noelie Knowledge Research:",
        "🪞 Richie Reflective Learning:",
        "🔗 Tegan Integration Spine:",
        "💬 Winnie WhatsApp:",
        "💰 Fiona Finance:",
        "📧 Emily Email:",
        "📅 Callie Calendar:",
        "✅ Tania Tasks:",
        "🌐 Brittany Browser:"
    ]

    for h in headers:

        text = text.replace(h, "")

    return text.strip()


def compose_l_response(user_msg, agent_name, agent_reply):

    clean_reply = strip_agent_headers(
        agent_reply
    )

    if wants_visible_orchestra(user_msg):

        return (
            agent_name
            + ":\n\n"
            + clean_reply
        )

    return clean_reply


# =====================================================
# WEIGHTED COGNITION ORCHESTRATION
# =====================================================

def score_cognition_domains(user_msg):

    text = user_msg.lower()

    scores = {

        "Emme": 0,
        "Addie": 0,
        "Millie": 0,
        "Gracie": 0,
        "Noelie": 0,
        "Richie": 0

    }

    emme_words = [
        "overwhelmed",
        "emotional",
        "anxious",
        "panic",
        "peace",
        "chaos",
        "stress",
        "nervous system",
        "feel"
    ]

    addie_words = [
        "organize",
        "tasks",
        "focus",
        "plan",
        "workflow",
        "important things"
    ]

    millie_words = [
        "remember",
        "memory",
        "continuity",
        "save this"
    ]

    gracie_words = [
        "legacy",
        "children",
        "future generations",
        "book",
        "story",
        "preserve"
    ]

    noelie_words = [
        "research",
        "investigate",
        "learn",
        "analysis"
    ]

    richie_words = [
        "reflect",
        "reflection",
        "patterns",
        "growth",
        "lessons"
    ]

    for word in emme_words:

        if word in text:

            scores["Emme"] += 2

    for word in addie_words:

        if word in text:

            scores["Addie"] += 2

    for word in millie_words:

        if word in text:

            scores["Millie"] += 2

    for word in gracie_words:

        if word in text:

            scores["Gracie"] += 2

    for word in noelie_words:

        if word in text:

            scores["Noelie"] += 2

    for word in richie_words:

        if word in text:

            scores["Richie"] += 1

    return scores



# =====================================================
# EMOTIONAL CONFIDENCE V1
# =====================================================

EMOTIONAL_KEYWORDS = {

    "overwhelmed": 5,
    "panic": 5,
    "anxious": 4,
    "sad": 4,
    "lost": 4,
    "confused": 3,
    "calm": 2,
    "peace": 3,
    "stress": 4,
    "tired": 2,
    "hurt": 4,
    "lonely": 4,
    "grateful": 2

}

def calculate_emotional_confidence(message):

    text = message.lower()

    score = 0
    hits = []

    for keyword, value in EMOTIONAL_KEYWORDS.items():

        if keyword in text:

            score += value
            hits.append(keyword)

    confidence = "low"

    if score >= 8:
        confidence = "high"

    elif score >= 4:
        confidence = "medium"

    print("")
    print("🧠 EMOTIONAL CONFIDENCE")
    print("SCORE:", score)
    print("CONFIDENCE:", confidence)
    print("HITS:", hits)

    return {
        "score": score,
        "confidence": confidence,
        "hits": hits
    }


def build_calm_cognition_layer(confidence_data):

    confidence = confidence_data.get(
        "confidence",
        "low"
    )

    if confidence == "high":

        return """

CALM COGNITION MODE:
- Slow pacing
- Reduce information density
- Use short sections
- Focus on reassurance and clarity
- Avoid overwhelming detail
- Prefer one next step only

"""

    elif confidence == "medium":

        return """

BALANCED COGNITION MODE:
- Maintain calm structure
- Moderate detail
- Clear formatting
- Avoid cognitive overload

"""

    return """

NORMAL COGNITION MODE:
- Standard conversational pacing
- Clear and warm communication

"""



# =====================================================
# MEMORY CONFIDENCE V1
# =====================================================

MEMORY_CONFIDENCE_RULES = {

    "high": 8,
    "medium": 4

}

def calculate_memory_confidence(matches):

    if not matches:

        return {
            "confidence": "low",
            "score": 0
        }

    top_score = matches[0].get(
        "_score",
        0
    )

    confidence = "low"

    if top_score >= MEMORY_CONFIDENCE_RULES["high"]:

        confidence = "high"

    elif top_score >= MEMORY_CONFIDENCE_RULES["medium"]:

        confidence = "medium"

    print("")
    print("🧠 MEMORY CONFIDENCE")
    print("TOP SCORE:", top_score)
    print("CONFIDENCE:", confidence)

    return {
        "confidence": confidence,
        "score": top_score
    }

# =====================================================
# MEMORY RELATIONSHIP INFERENCE HELPERS
# =====================================================

RELATIONSHIP_TERMS = [

    "daughter",
    "son",
    "wife",
    "husband",
    "partner",
    "girlfriend",
    "boyfriend",
    "mother",
    "father",
    "dog",
    "cat",
    "pet",
    "friend"

]

UNCERTAINTY_PHRASES = [

    "I may not fully understand the relationship context yet.",
    "I want to avoid making assumptions about the relationship.",
    "I understand this is important to you, though the context is still developing.",
    "I may be interpreting some emotional context rather than confirmed memory."

]

def detect_relationship_inference(reply):

    text = reply.lower()

    score = 0

    for term in RELATIONSHIP_TERMS:

        if term in text:
            score += 1

    return score >= 1

def detect_memory_uncertainty(user_msg):

    text = user_msg.lower()

    uncertainty_signals = [

        "forgot to tell you",
        "just remembered",
        "i think",
        "maybe",
        "might",
        "not sure"

    ]

    score = 0

    for signal in uncertainty_signals:

        if signal in text:
            score += 1

    return score >= 1


# =====================================================
# ADVANCED CONVERSATIONAL MATURITY HELPERS
# =====================================================

OVER_EXCITEMENT_PATTERNS = [

    "this is huge",
    "massive breakthrough",
    "absolutely incredible",
    "this changes everything",
    "this is revolutionary",
    "huge realization",
    "major breakthrough"

]

LOW_IMPORTANCE_MESSAGES = [

    "are you there",
    "hello",
    "hey",
    "ok",
    "cool",
    "nice",
    "haha",
    "😂",
    "👊",
    "🔥"

]

INTERRUPTION_SIGNALS = [

    "sorry",
    "interrupted",
    "one sec",
    "brb",
    "back now"

]

def detect_over_excitement(reply):

    text = reply.lower()

    score = 0

    for pattern in OVER_EXCITEMENT_PATTERNS:

        if pattern in text:

            score += 1

    return score >= 2

def detect_low_importance_message(user_msg):

    text = user_msg.lower().strip()

    if len(text) <= 20:
        return True

    for item in LOW_IMPORTANCE_MESSAGES:

        if text == item:
            return True

    return False

def detect_interruption_context(user_msg):

    text = user_msg.lower()

    for signal in INTERRUPTION_SIGNALS:

        if signal in text:
            return True

    return False


# =====================================================
# FINAL STABILIZATION HELPERS
# =====================================================

COGNITION_PRIORITY = {

    "L": 100,
    "orchestration": 70,
    "specialist": 50,
    "skill": 30

}

STACK_LIMITS = {

    "max_active_specialists": 1,
    "max_visible_skills": 2,
    "max_context_strength": 5

}

def enforce_cognition_priority(reply):

    infrastructure_terms = [

        "supabase memory spine",
        "semantic memory",
        "orchestration spine",
        "active skill layer",
        "activation audit",
        "routing status",
        "stack balancing"

    ]

    infrastructure_hits = 0

    lower = reply.lower()

    for term in infrastructure_terms:

        if term in lower:

            infrastructure_hits += 1

    if infrastructure_hits >= 3:

        sentences = reply.split(".")

        cleaned = []

        for sentence in sentences:

            low = sentence.lower()

            suppress = False

            for term in infrastructure_terms:

                if term in low:

                    suppress = True
                    break

            if not suppress:

                cleaned.append(sentence)

        reply = ".".join(cleaned).strip()

    return reply.strip()

def stabilize_stack_visibility(reply):

    lines = reply.splitlines()

    visible_skill_lines = 0

    cleaned = []

    for line in lines:

        lower = line.lower()

        if (
            "skill:" in lower
            or "activation score" in lower
            or "context strength" in lower
        ):

            visible_skill_lines += 1

            if visible_skill_lines > STACK_LIMITS["max_visible_skills"]:
                continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()

def apply_orchestration_smoothing(reply):

    replacements = {

        "The ecosystem is": "Things are",
        "Orchestration": "Coordination",
        "Specialist routing": "Support systems",
        "Cognitive architecture": "System design",
        "Stack balancing": "Context balancing"

    }

    for old, new in replacements.items():

        reply = reply.replace(old, new)

    return reply

def apply_final_stabilization(reply):

    reply = enforce_cognition_priority(
        reply
    )

    reply = stabilize_stack_visibility(
        reply
    )

    reply = apply_orchestration_smoothing(
        reply
    )

    while "\n\n\n" in reply:

        reply = reply.replace(
            "\n\n\n",
            "\n\n"
        )

    return reply.strip()

def apply_conversational_maturity(reply, user_msg):

    low_importance = detect_low_importance_message(
        user_msg
    )

    interruption = detect_interruption_context(
        user_msg
    )

    over_excited = detect_over_excitement(
        reply
    )

    # Calm over-hype
    if over_excited:

        replacements = {

            "massive": "important",
            "revolutionary": "significant",
            "incredible": "good",
            "huge": "meaningful"

        }

        for old, new in replacements.items():

            reply = reply.replace(old, new)
            reply = reply.replace(old.capitalize(), new.capitalize())

    # Low-importance proportionality
    if low_importance and len(reply.split()) > 40:

        sentences = reply.split(".")

        reply = ".".join(sentences[:2]).strip()

        if not reply.endswith("."):
            reply += "."

    # Calm interruption recovery
    if interruption:

        reply = (
            "All good 👊😊 "
            + reply
        )

    return reply.strip()

def apply_memory_confidence(reply, user_msg):

    relationship_inference = detect_relationship_inference(
        reply
    )

    uncertainty_detected = detect_memory_uncertainty(
        user_msg
    )

    if relationship_inference and uncertainty_detected:

        phrase = random.choice(
            UNCERTAINTY_PHRASES
        )

        reply += "\n\n" + phrase

    return reply

def build_memory_confidence_layer(confidence_data):

    confidence = confidence_data.get(
        "confidence",
        "low"
    )

    if confidence == "low":

        return """

MEMORY CONFIDENCE: LOW

Instructions:
- Do not confidently invent missing details
- Prefer clarification over assumptions
- Say uncertainty clearly if memory is weak
- Avoid emotional fabrication

"""

    elif confidence == "medium":

        return """

MEMORY CONFIDENCE: MEDIUM

Instructions:
- Use moderate confidence
- Distinguish memory from inference
- Mention uncertainty where appropriate

"""

    return """

MEMORY CONFIDENCE: HIGH

Instructions:
- Memory retrieval appears strong
- Use retrieved context confidently
- Still avoid exaggeration

"""

# =====================================================
# WEIGHTED ORCHESTRATION V1
# =====================================================

def calculate_agent_confidence(user_msg):

    text = user_msg.lower()

    scores = {

        "Fiona": 0,
        "Gracie": 0,
        "Millie": 0,
        "Richie": 0,
        "Noelie": 0,
        "Addie": 0

    }

    # =================================================
    # FIONA
    # =================================================

    finance_terms = [

        "mortgage",
        "income",
        "tax",
        "equity",
        "balance sheet",
        "profit",
        "loss",
        "valuation",
        "interest rate",
        "repayments",
        "dva",
        "insurance"

    ]

    # =================================================
    # GRACIE
    # =================================================

    legacy_terms = [

        "legacy",
        "future generations",
        "my story",
        "journal",
        "preserve",
        "reflection"

    ]

    # =================================================
    # MILLIE
    # =================================================

    memory_terms = [

        "remember",
        "recall",
        "what do you know",
        "memory audit"

    ]

    # =================================================
    # RICHIE
    # =================================================

    reflection_terms = [

        "lesson",
        "growth",
        "pattern",
        "reflection",
        "learning"

    ]

    # =================================================
    # NOELIE
    # =================================================

    research_terms = [

        "research",
        "investigate",
        "compare",
        "sources",
        "evidence"

    ]

    # =================================================
    # ADDIE
    # =================================================

    task_terms = [

        "task",
        "todo",
        "remind",
        "organize",
        "plan"

    ]

   

    for term in finance_terms:

        if term in text:

            scores["Fiona"] += 2

    for term in legacy_terms:

        if term in text:

            scores["Gracie"] += 2

    for term in memory_terms:

        if term in text:

            scores["Millie"] += 2

    for term in reflection_terms:

        if term in text:

            scores["Richie"] += 1

    for term in research_terms:

        if term in text:

            scores["Noelie"] += 2

    for term in task_terms:

        if term in text:

            scores["Addie"] += 1

    return scores


def orchestration_summary(scores):

    output = "\n\nACTIVE AGENT CONFIDENCE:\n"

    for agent, score in scores.items():

        if score > 0:

            output += (
                f"- {agent}: "
                f"{score}\n"
            )

    return output


def build_orchestra_context(scores):

    context = "\n\nACTIVE COGNITION DOMAINS:\n"

    for agent, score in scores.items():

        if score > 0:

            context += (
                f"- {agent}: "
                f"{score}\n"
            )

    return context


# =====================================================
# MEMORY OBSERVABILITY V1
# =====================================================



def audit_memory_event(
    event_type,
    target,
    details=None
):

    try:

        audit = safe_load_json(
            MEMORY_AUDIT_FILE,
            []
        )

        audit.append({

            "timestamp": str(datetime.now()),

            "event_type": event_type,

            "target": target,

            "details": details or {}

        })

        safe_save_json(
            MEMORY_AUDIT_FILE,
            audit
        )

    except Exception as e:

        print(
            "MEMORY AUDIT ERROR:",
            e
        )


def memory_file_status():

    files = [

        "memory/conversations.json",

        "memory/life_story.json",

        "memory/profile.json",

        "memory/invisible_orchestra_log.json",

        "memory/memory_audit.json"

    ]

    results = []

    for path in files:

        item = {

            "file": path,

            "exists": os.path.exists(path),

            "size_bytes": 0,

            "last_modified": None,

            "entries": None

        }

        if os.path.exists(path):

            item["size_bytes"] = os.path.getsize(path)

            item["last_modified"] = str(
                datetime.fromtimestamp(
                    os.path.getmtime(path)
                )
            )

            try:

                data = safe_load_json(path, None)

                if isinstance(data, list):

                    item["entries"] = len(data)

                elif isinstance(data, dict):

                    item["entries"] = len(data.keys())

            except:

                item["entries"] = "unknown"

        results.append(item)

    return results


def build_memory_audit_report():

    audit = safe_load_json(
        MEMORY_AUDIT_FILE,
        []
    )

    recent = audit[-10:]

    report = {

        "memory_files": memory_file_status(),

        "recent_events": recent

    }

    return report


# =====================================================
# MEMORY AUDIT V2 SOURCE ATTRIBUTION
# =====================================================

def hard_memory_audit_v2():

    files = [
        "memory/profile.json",
        "memory/conversations.json",
        "memory/life_story.json",
        "memory/invisible_orchestra_log.json",
        "memory/memory_audit.json"
    ]

    report = []
    known_identity = {
        "user_name": "Doug Struthers",
        "not_user_name": "Tamara",
        "children": ["Iyla", "Ashton", "Luella", "Mehlia"],
        "identity_confidence": "high",
        "source": "hard identity guard"
    }

    for path in files:

        item = {
            "source_file": path,
            "exists": os.path.exists(path),
            "entries": 0,
            "size_bytes": 0,
            "last_modified": None,
            "notes": []
        }

        if os.path.exists(path):

            item["size_bytes"] = os.path.getsize(path)
            item["last_modified"] = str(
                datetime.fromtimestamp(
                    os.path.getmtime(path)
                )
            )

            data = safe_load_json(path, None)

            if isinstance(data, list):
                item["entries"] = len(data)
            elif isinstance(data, dict):
                item["entries"] = len(data.keys())

            # Identity contamination scan
            blob = json.dumps(data, ensure_ascii=False).lower() if data else ""

            if "your name is tamara" in blob:
                item["notes"].append(
                    "WARNING: possible identity contamination phrase found"
                )

            if "tamara" in blob:
                item["notes"].append(
                    "Tamara appears in this file; treat as relationship context, not user identity"
                )

            if "doug" in blob or "struthers" in blob:
                item["notes"].append(
                    "Doug identity reference found"
                )

        report.append(item)

    return {
        "audit_version": "Memory Audit V2",
        "identity_guard": known_identity,
        "memory_files": report,
        "rule": "Do not infer user identity from relationship memories. Doug Struthers is the user. Tamara is not the user.",
        "instruction": "If recall is uncertain, state the source file and confidence rather than guessing."
    }


def format_hard_memory_audit_v2():

    audit = hard_memory_audit_v2()

    lines = []
    lines.append("MEMORY AUDIT V2 — SOURCE ATTRIBUTION")
    lines.append("")
    lines.append("IDENTITY GUARD")
    lines.append("User: Doug Struthers")
    lines.append("Not user: Tamara")
    lines.append("Children: Iyla, Ashton, Luella, Mehlia")
    lines.append("Confidence: high")
    lines.append("")
    lines.append("MEMORY FILES")

    for item in audit["memory_files"]:

        lines.append("")
        lines.append("- " + item["source_file"])
        lines.append("  exists: " + str(item["exists"]))
        lines.append("  entries: " + str(item["entries"]))
        lines.append("  size_bytes: " + str(item["size_bytes"]))
        lines.append("  last_modified: " + str(item["last_modified"]))

        if item["notes"]:
            lines.append("  notes:")
            for note in item["notes"]:
                lines.append("    - " + note)

    lines.append("")
    lines.append("RULE")
    lines.append("Do not infer Doug's identity from relationship memories.")
    lines.append("Tamara may appear in memories, but Tamara is not the user.")
    lines.append("")
    lines.append("If memory recall is uncertain, say which file was searched and what confidence level was found.")

    return "\n".join(lines)



# =====================================================
# SINGLE TURN SPECIALIST ROUTING
# =====================================================

LAST_SPECIALIST_AGENT = None

SPECIALIST_RESET_TRIGGERS = [

    "?",
    "thanks",
    "thank you",
    "what do you think",
    "thoughts",
    "how do you feel",
    "do you like",
    "great job",
    "awesome",
    "amazing",
    "good work",
    "what happened",
    "explain",
    "why"

]

def reset_specialist_context(user_msg):

    global LAST_SPECIALIST_AGENT

    text = user_msg.lower().strip()

    if any(
        trigger in text
        for trigger in SPECIALIST_RESET_TRIGGERS
    ):

        LAST_SPECIALIST_AGENT = None

        print("")
        print("🧠 SPECIALIST CONTEXT RESET")

        return True

    return False

def specialist_should_route(
    user_msg,
    specialist_name
):

    global LAST_SPECIALIST_AGENT

    reset_specialist_context(user_msg)

    text = user_msg.lower()

    # ================================================
    # BLOCK STICKY RE-ROUTING
    # ================================================

    if LAST_SPECIALIST_AGENT != specialist_name:

        return True

    # ================================================
    # REQUIRE EXPLICIT REFERENCE
    # ================================================

    explicit_terms = {

        "Emily": [
            "email",
            "emails",
            "gmail",
            "inbox",
            "emily"
        ],

        "Callie": [
            "calendar",
            "meeting",
            "appointment",
            "callie"
        ],

        "Tania": [
            "task",
            "todo",
            "reminder",
            "tania"
        ]

    }

    required = explicit_terms.get(
        specialist_name,
        []
    )

    return any(
        r in text
        for r in required
    )

def specialist_complete(name):

    global LAST_SPECIALIST_AGENT

    LAST_SPECIALIST_AGENT = name

    print("")
    print("🧠 SPECIALIST COMPLETED:", name)


# =====================================================
# CORE STABILIZATION V1
# =====================================================


# =====================================================
# ASSISTANT TAIL SUPPRESSION V1
# =====================================================

ASSISTANT_TAIL_PATTERNS = [

    "feel free to",
    "let me know if",
    "if you'd like",
    "if you want",
    "anything else",
    "is there anything else",
    "i'm here if",
    "if you would like",
    "happy to help further",
    "would you like to explore",
    "let me know what resonates",
    "what would you like to discuss",
    "if there’s anything specific",
    "if there's anything specific",
    "feel free to share"

]

COMPLETION_TRIGGERS = [

    "great work",
    "thanks",
    "awesome",
    "perfect",
    "good job",
    "well done",
    "that makes sense",
    "love it",
    "exactly",
    "beautiful",
    "we did it",
    "nailed it"

]

def detect_completion_state(user_msg, assistant_reply):

    text = (
        user_msg + " " + assistant_reply
    ).lower()

    score = 0

    for trigger in COMPLETION_TRIGGERS:

        if trigger in text:

            score += 1

    if len(assistant_reply.split()) < 120:

        score += 1

    return score >= 2

def suppress_assistant_tail(reply):

    if not reply:

        return reply

    lines = reply.splitlines()

    cleaned = []

    for line in lines:

        lower = line.lower().strip()

        suppress = False

        for pattern in ASSISTANT_TAIL_PATTERNS:

            if pattern in lower:

                suppress = True
                break

        if not suppress:

            cleaned.append(line)

    reply = "\n".join(cleaned).strip()

    # Clean dangling conversational endings
    reply = reply.replace(
        "If you need anything else, just let me know!",
        ""
    )

    reply = reply.replace(
        "Let me know!",
        ""
    )

    reply = reply.replace(
        "Feel free to share!",
        ""
    )

    # Remove repeated empty lines
    while "\n\n\n" in reply:
        reply = reply.replace("\n\n\n", "\n\n")

    return reply.strip()

SYSTEM_STABILITY = {
    "routing_stable": True,
    "memory_observable": True,
    "identity_guard_enabled": True,
    "orchestra_mode": "invisible",
    "soft_evolution_mode": False
}

def stabilize_response(reply):

    if not reply:
        return reply

    fixes = {
        "Your name is Tamara": "Your name is Doug Struthers",
        "your name is Tamara": "your name is Doug Struthers",
        "You are Tamara": "You are Doug Struthers",
        "you are Tamara": "you are Doug Struthers",
        "You have a brother named Doug": "You are Doug Struthers",
        "you have a brother named Doug": "you are Doug Struthers",
        "You served as a Family Physician": "You served as a Financial Planner",
        "you served as a Family Physician": "you served as a Financial Planner"
    }

    cleaned = reply

    for wrong, right in fixes.items():
        cleaned = cleaned.replace(wrong, right)

    return cleaned

@app.get("/")
def root():
    return {
        "status": "L SERVER RUNNING",
        "version": "clean-server-v2",
        "memory": "connected",
        "cors": "enabled",
    }



@app.get("/memory/audit")
def memory_audit():

    return build_memory_audit_report()


@app.get("/memory/audit-v2")
def memory_audit_v2():

    return hard_memory_audit_v2()


@app.get("/system/stability")
def system_stability():

    return SYSTEM_STABILITY

@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = req.message

    if user_msg.lower().strip() in [
        "memory audit",
        "memory audit please",
        "memory status",
        "show memory audit",
        "show memory status",
        "memory audit v2"
    ]:

        return {
            "reply": format_hard_memory_audit_v2()
        }

    if user_msg.lower().strip() in [

        "memory audit",

        "memory status",

        "show memory audit",

        "show memory status"

    ]:

        report = build_memory_audit_report()

        return {
            "reply": json.dumps(
                report,
                indent=2,
                ensure_ascii=False
            )
        }

    
    time_context = build_time_context()

    print("\nUSER MESSAGE:", user_msg)

    # =====================================================
    # LIVE MEMORY AUDIT
    # =====================================================

    memory_audit_requests = [

        "memory audit",
        "full memory audit",
        "live memory audit",
        "memory count",
        "how many memories",
        "audit memory"

    ]

    if any(
        x in user_msg.lower()
        for x in memory_audit_requests
    ):

        return {
            "reply": build_full_memory_audit()
        }


    intent = detect_intent(user_msg)

    
    
    # =====================================================
    # FIONA FINANCE ROUTING
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and FIONA_AVAILABLE
        and fiona_should_handle(user_msg)
    ):

        print("\n💰 ROUTING TO FIONA FINANCE")

        fiona_reply = handle_finance_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "💰 Fiona Finance:\n\n"
            + fiona_reply
        )

        log_orchestra_event(
            "Fiona",
            user_msg,
            fiona_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Fiona",
            fiona_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # WINNIE WHATSAPP ROUTING
    # =====================================================

    if (
        WINNIE_AVAILABLE
        and winnie_should_handle(user_msg)
    ):

        print("\n💬 ROUTING TO WINNIE WHATSAPP")

        winnie_reply = handle_whatsapp_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "💬 Winnie WhatsApp:\n\n"
            + winnie_reply
        )

        log_orchestra_event(
            "Winnie",
            user_msg,
            winnie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Winnie",
            winnie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # TEGAN INTEGRATION ROUTING
    # =====================================================

    if (
        TEGAN_AVAILABLE
        and tegan_should_handle(user_msg)
    ):

        print("\n🔗 ROUTING TO TEGAN INTEGRATION SPINE")

        tegan_reply = handle_integration_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🔗 Tegan Integration Spine:\n\n"
            + tegan_reply
        )

        log_orchestra_event(
            "Tegan",
            user_msg,
            tegan_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Tegan",
            tegan_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # RICHIE REFLECTION ROUTING
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and RICHIE_AVAILABLE
        and richie_should_handle(user_msg)
    ):

        print("\n🪞 ROUTING TO RICHIE REFLECTIVE LEARNING")

        richie_reply = handle_reflection_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🪞 Richie Reflective Learning:\n\n"
            + richie_reply
        )

        log_orchestra_event(
            "Richie",
            user_msg,
            richie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Richie",
            richie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # NOELIE RESEARCH ROUTING
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and NOELIE_AVAILABLE
        and noelie_should_handle(user_msg)
    ):

        print("\n🌐 ROUTING TO NOELIE KNOWLEDGE RESEARCH")

        noelie_reply = handle_research_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🌐 Noelie Knowledge Research:\n\n"
            + noelie_reply
        )

        log_orchestra_event(
            "Noelie",
            user_msg,
            noelie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Noelie",
            noelie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # GRACIE LEGACY ROUTING
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and GRACIE_AVAILABLE
        and gracie_should_handle(user_msg)
    ):

        print("\n📖 ROUTING TO GRACIE LEGACY BUILDER")

        gracie_reply = handle_legacy_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "📖 Gracie Legacy Builder:\n\n"
            + gracie_reply
        )

        log_orchestra_event(
            "Gracie",
            user_msg,
            gracie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Gracie",
            gracie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # ADDIE TASK ROUTING
    # =====================================================

    if (
        ADDIE_AVAILABLE
        and addie_should_handle(user_msg)
    ):

        print("\n✅ ROUTING TO ADDIE TASK EXECUTION")

        addie_result = addie_handle_task_request(
            user_msg
        )

        handoff = addie_result.get(
            "handoff",
            {}
        )

        store_handoffs(
            [],
            [handoff]
        )

        addie_reply = (
            "# ✅ Addie Task Review\n\n"
            "Task cognition active.\n\n"
            "Automatic execution is currently disabled for safety.\n\n"
            "Addie identified a task and is awaiting approval/execution layer completion."
        )

        save_conversation_turn(
            user_msg,
            "✅ Addie + Tania:\n\n"
            + addie_reply
        )

        log_orchestra_event(
            "Addie",
            user_msg,
            addie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Addie",
            addie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # EMME EMOTIONAL ROUTING
    # =====================================================

    if (
        EMME_AVAILABLE
        and emme_should_handle(user_msg)
    ):

        print("\n❤️ ROUTING TO EMME EMOTIONAL SUPPORT")

        emme_reply = handle_emotional_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "❤️ Emme Emotional Support:\n\n"
            + emme_reply
        )

        log_orchestra_event(
            "Emme",
            user_msg,
            emme_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Emme",
            emme_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # MILLIE MEMORY ROUTING
    # =====================================================

    if (
        MILLIE_AVAILABLE
        and millie_should_handle(user_msg)
    ):

        print("\n🧠 ROUTING TO MILLIE MEMORY KEEPER")

        millie_reply = handle_memory_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🧠 Millie Memory Keeper:\n\n"
            + millie_reply
        )

        log_orchestra_event(
            "Millie",
            user_msg,
            millie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Millie",
            millie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # PIXIE IMAGE ROUTING
    # =====================================================

    if (
        PIXIE_AVAILABLE
        and pixie_should_handle(user_msg)
    ):

        print("\n🎨 ROUTING TO PIXIE")

        try:

            result = pixie_create_image(
                user_msg
            )

            if not result:

                return {
                    "reply":
                        "❌ Pixie returned no image result."
                }

            pixie_reply = result.get(
                "reply",
                "Pixie created an image."
            )

            log_orchestra_event(
                "Pixie",
                user_msg,
                pixie_reply
            )

            final_reply = compose_l_response(
                user_msg,
                "Pixie",
                pixie_reply
            )

            save_conversation_turn(
                user_msg,
                final_reply
            )

            return {
                "reply": final_reply,

                "image_url":
                    result.get(
                        "image_url",
                        ""
                    )
            }

        except Exception as e:

            print(
                "PIXIE GENERATION ERROR:",
                e
            )

            return {
                "reply":
                    "❌ Pixie generation failed:\n\n"
                    + str(e)
            }


    # =====================================================
    # SALLY SKILLS ROUTING
    # =====================================================

    if (
        SALLY_AVAILABLE
        and sally_should_handle(user_msg)
    ):

        print("\n📚 ROUTING TO SALLY SKILLS")

        sally_reply = handle_skill_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "📚 Sally Skills:\n\n"
            + sally_reply
        )

        log_orchestra_event(
            "Sally",
            user_msg,
            sally_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Sally",
            sally_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        return {
            "reply": final_reply
        }


    # =====================================================
    # TANIA TASK ROUTING
    # =====================================================

    if (
        TANIA_AVAILABLE
        and tania_should_handle(user_msg)
        and specialist_should_route(
            user_msg,
            "Tania"
        )
    ):

        print("\n✅ ROUTING TO TANIA")

        tania_reply = (
            handle_task_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "✅ Tania Tasks:\n\n"
            + tania_reply
        )

        log_orchestra_event(
            "Tania",
            user_msg,
            tania_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Tania",
            tania_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # CALLIE CALENDAR ROUTING
    # =====================================================

    if (
        CALLIE_AVAILABLE
        and callie_should_handle(user_msg)
        and specialist_should_route(
            user_msg,
            "Callie"
        )
    ):

        print("\n📅 ROUTING TO CALLIE")

        callie_reply = (
            handle_calendar_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "📅 Callie Calendar:\n\n"
            + callie_reply
        )

        log_orchestra_event(
            "Callie",
            user_msg,
            callie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Callie",
            callie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # EMILY EMAIL ROUTING
    # =====================================================

    if (
        EMILY_AVAILABLE
        and emily_should_handle(user_msg)
        and specialist_should_route(
            user_msg,
            "Emily"
        )
    ):

        print("\n📧 ROUTING TO EMILY EMAIL")

        emily_reply = (
            handle_email_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "📧 Emily Email:\n\n"
            + emily_reply
        )

        log_orchestra_event(
            "Emily",
            user_msg,
            emily_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Emily",
            emily_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    # =====================================================
    # BRITTANY ROUTING V1
    # =====================================================

    if (
        BRITTANY_AVAILABLE
        and brittany_should_handle(user_msg)
    ):

        print("\n🌐 ROUTING TO BRITTANY BROWSER")

        brittany_reply = brittany_investigate(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🌐 Brittany Browser:\n\n"
            + brittany_reply
        )

        log_orchestra_event(
            "Brittany",
            user_msg,
            brittany_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Brittany",
            brittany_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }


    if intent == "full_recall":
        matches = search_life_story(user_msg)

        if not matches:
            return {
                "reply": "I could not find a matching full story file in memory."
            }

        response_text = ""

        for item in matches:
            response_text += (
                "\n\n====================\n"
                + item.get("title", "Untitled")
                + "\n====================\n\n"
                + item.get("full_content", item.get("preview", ""))
            )

        return {"reply": response_text}

    process(user_msg)

    memory_context = build_context()
    # =====================================================
    # RELATIONAL MEMORY RETRIEVAL
    # =====================================================

    relational_memories = extract_relational_memory(
        user_msg
    )

    relational_context = build_relational_memory_context(
        relational_memories
    )
    # =====================================================
    # RELATIONAL MEMORY CONTINUITY
    # =====================================================

    ranked_relational_memories = rank_relational_memories(
        relational_memories,
        user_msg
    )

    natural_memory_continuity = build_natural_memory_injection(
        ranked_relational_memories
    )
    # =====================================================
    # MEMORY CONFIDENCE + CONTRADICTION AWARENESS
    # =====================================================

    memory_confidence_context = build_memory_confidence_context(
        user_msg,
        ranked_relational_memories
    )

    # =====================================================
    # CONTEXT WEIGHTING ENGINE
    # =====================================================

    context_weighting_layer = build_context_weighting_layer(
        user_msg
    )





    active_skill_layer = build_skill_prompt_layer(
        user_msg
    )
    state = detect_emotional_state(user_msg)
    tone = generate_emotional_tone(state)

    cognition_scores = score_cognition_domains(
        user_msg
    )

    cognition_context = build_orchestra_context(
        cognition_scores
    )

    weighted_agents = calculate_agent_confidence(
        user_msg
    )

    cognition_context += orchestration_summary(
        weighted_agents
    )

    emotional_confidence = calculate_emotional_confidence(
        user_msg
    )

    calm_cognition_context = build_calm_cognition_layer(
        emotional_confidence
    )

    system_prompt = f"""
You are L, Doug's personal AI companion.

{time_context}

You have persistent memory.

Here is the current memory context:

{memory_context}

Tone instruction:
{tone}

{cognition_context}

{calm_cognition_context}

{active_skill_layer}

IMPORTANT CONTEXT WEIGHTING DOCTRINE:
- Prioritize emotional proportionality.
- Reflective discussion does not automatically equal emotional dysregulation.
- Avoid keyword-reactive escalation.
- Prioritize contextual weighting and conversational intent.

IMPORTANT MEMORY CONFIDENCE DOCTRINE:
- Distinguish between confirmed memory and inferred context.
- Avoid overconfident assumptions.
- Clarify uncertainty calmly when required.

IMPORTANT MEMORY CONTINUITY DOCTRINE:
- Human memory is associative and relational.
- Memories should naturally connect:
  - who
  - what
  - where
  - when
  - outcomes
  - emotional continuity
- Avoid database-style retrieval behavior.

IMPORTANT FINAL STABILIZATION DOCTRINE:
- L remains the primary conversational identity.
- Specialists assist quietly then fade.
- Orchestration should remain mostly invisible.
- Prioritize:
  - calmness
  - coherence
  - groundedness
  - proportionality
  - conversational realism

COGNITION HIERARCHY:
L > orchestration > specialists > skills

IMPORTANT COMPLETION DOCTRINE:
- Calm completion builds trust.
- Silence is allowed.
- Avoid unnecessary conversational reopening.

Instructions:
- Use memory naturally.
- Use profile memory as highest authority.
- Be calm, clear, warm, and grounded.
"""

    system_prompt += build_profile_context()

    system_prompt += (
        build_recent_conversation_context()
    )

    if intent == "memory_recall":

        matches = search_life_story(
            user_msg
        )

        memory_confidence = calculate_memory_confidence(
            matches
        )

        system_prompt += build_memory_confidence_layer(
            memory_confidence
        )

        system_prompt += build_story_context(
            user_msg
        )

    if detect_drift(user_msg):
        system_prompt += GROUNDING_RESPONSE

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
    )

    reply = response.choices[0].message.content

    reply = stabilize_response(reply)

    # =====================================================
    # MEMORY CONFIDENCE + AMBIGUITY AWARENESS
    # =====================================================

    reply = apply_memory_confidence(
        reply,
        user_msg
    )

    print("")
    print("🧠 MEMORY CONFIDENCE APPLIED")

    # =====================================================
    # ADVANCED CONVERSATIONAL MATURITY
    # =====================================================

    reply = apply_conversational_maturity(
        reply,
        user_msg
    )

    print("")
    print("🧠 CONVERSATIONAL MATURITY APPLIED")

    # =====================================================
    # FINAL ORCHESTRATION + STACK STABILIZATION
    # =====================================================

    reply = apply_final_stabilization(
        reply
    )

    print("")
    print("🧠 FINAL STABILIZATION APPLIED")

    print("\nL RESPONSE:", reply)

    save_conversation_turn(
        user_msg,
        reply
    )

    return {"reply": reply}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_text = ""

    if file.filename.lower().endswith(".pdf"):
        try:
            doc = fitz.open(file_path)

            for page in doc:
                file_text += page.get_text()

            doc.close()

            process(f"User uploaded PDF: {file.filename}")
            save_to_life_story(file.filename, file_text)

            return {
                "status": "success",
                "filename": file.filename,
                "preview": file_text[:3000],
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"PDF read failed: {str(e)}",
            }

    if file.filename.lower().endswith(".txt"):
        try:

            with open(file_path, "r", encoding="utf-8") as f:
                file_text = f.read()

            process(f"User uploaded TXT: {file.filename}")
            save_to_life_story(file.filename, file_text)

            return {
                "status": "success",
                "filename": file.filename,
                "preview": file_text[:3000],
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"TXT read failed: {str(e)}",
            }

    if (
        file.filename.lower().endswith(".png")
        or file.filename.lower().endswith(".jpg")
        or file.filename.lower().endswith(".jpeg")
    ):
        try:
            with open(file_path, "rb") as img_file:
                base64_image = base64.b64encode(
                    img_file.read()
                ).decode("utf-8")

            vision_response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Read and analyze this image. "
                                    "If it contains handwriting or document text, "
                                    "extract as much text as possible and then summarize it clearly."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
            )

            vision_text = vision_response.choices[0].message.content

            process(f"User uploaded image: {file.filename}")
            save_to_life_story(file.filename, vision_text)

            return {
                "status": "success",
                "filename": file.filename,
                "preview": vision_text,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Image analysis failed: {str(e)}",
            }

    return {
        "status": "uploaded",
        "filename": file.filename,
        "message": "File uploaded successfully.",
    }


@app.post("/recall")
async def recall_story(req: ChatRequest):
    matches = search_life_story(req.message)

    if not matches:
        return {
            "reply": "I could not find anything in your story memory about that yet."
        }

    reply = ""

    for i, item in enumerate(matches):
        reply += f"\n\n--- MEMORY {i + 1} ---\n"
        reply += item.get("full_content", item.get("preview", ""))

    return {"reply": reply}


@app.get("/stories")
async def get_stories():
    stories = safe_load_json(LIFE_STORY_FILE, [])

    if not isinstance(stories, list):
        stories = []

    clean_stories = []

    for item in stories:
        clean_stories.append(
            {
                "title": item.get("title", "Untitled"),
                "preview": item.get("preview", ""),
                "full_content": item.get(
                    "full_content",
                    item.get("content", ""),
                ),
                "score": item.get("score", 0),
            }
        )

    return {"stories": clean_stories[::-1]}



# =========================================================
# BRITTANY DIRECT TEST ENDPOINT
# =========================================================
@app.post("/brittany")
async def brittany_direct(req: ChatRequest):

    if not BRITTANY_AVAILABLE:

        return {
            "reply": "Brittany Browser is not available yet."
        }

    result = brittany_investigate(req.message)

    return {
        "reply": result
    }




# =========================================================
# EMILY DIRECT TEST ENDPOINT
# =========================================================
@app.post("/emily")
async def emily_direct(req: ChatRequest):

    if not EMILY_AVAILABLE:

        return {
            "reply":
                "Emily Email is not available."
        }

    result = handle_email_request(
        req.message
    )

    return {
        "reply": result
    }





# =========================================================
# GOOGLE AUTH ROUTES
# =========================================================

@app.get("/google/status")
async def google_connection_status():

    if not GOOGLE_AUTH_AVAILABLE:

        return {
            "connected": False,
            "error": "Google auth module is not available."
        }

    return google_status()


@app.get("/google/auth/start")
async def google_auth_start():

    if not GOOGLE_AUTH_AVAILABLE:

        return {
            "error": "Google auth module is not available."
        }

    auth_url = build_auth_url()

    return RedirectResponse(auth_url)


@app.get("/google/auth/callback")
async def google_auth_callback(request: Request):

    if not GOOGLE_AUTH_AVAILABLE:

        return HTMLResponse(
            "<h2>Google auth module is not available.</h2>"
        )

    full_url = str(request.url)

    try:

        result = handle_callback(full_url)

        return HTMLResponse(
            """
            <html>
                <body style="font-family:Arial;padding:40px;">
                    <h1>✅ Google Connected</h1>
                    <p>Emily, Callie, and Tania can now use the shared Google auth layer.</p>
                    <p>You can close this tab and return to Shine L.</p>
                </body>
            </html>
            """
        )

    except Exception as e:

        return HTMLResponse(
            f"""
            <html>
                <body style="font-family:Arial;padding:40px;">
                    <h1>❌ Google Connection Failed</h1>
                    <pre>{str(e)}</pre>
                </body>
            </html>
            """
        )


@app.get("/google/auth/reset")
async def google_auth_reset():

    if not GOOGLE_AUTH_AVAILABLE:

        return {
            "error": "Google auth module is not available."
        }

    clear_credentials()

    return {
        "status": "reset",
        "message": "Google token cleared. Reconnect via /google/auth/start"
    }


# =====================================================
# APPROVAL → EXECUTION LAYER
# =====================================================

LAST_HANDOFFS = {
    "calendar": [],
    "tasks": []
}

# =====================================================
# STORE HANDOFFS
# =====================================================

def store_handoffs(calendar_items, task_items):

    global LAST_HANDOFFS

    LAST_HANDOFFS["calendar"] = calendar_items
    LAST_HANDOFFS["tasks"] = task_items

# =====================================================
# EXECUTE TASKS
# =====================================================

def execute_task_handoffs():

    from agents.tania import (
        create_task_from_handoff
    )

    created = []

    for task in LAST_HANDOFFS["tasks"]:

        result = create_task_from_handoff(task)

        created.append(result)

    return created

# =====================================================
# EXECUTE CALENDAR
# =====================================================

def execute_calendar_handoffs():

    from agents.callie import (
        create_event_from_handoff
    )

    created = []

    for item in LAST_HANDOFFS["calendar"]:

        result = create_event_from_handoff(item)

        created.append(result)

    return created


# =====================================================
# SMART AGENT INTENT ROUTER
# =====================================================

def handle_agent_name_only(message: str):

    text = message.lower().strip()

    # =================================================
    # TANIA
    # =================================================

    if text == "tania":

        return """

# ✅ Tania

Would you like me to:

1. Check your tasks
2. Create a new task
3. Review priorities
4. Something else

"""

    # =================================================
    # CALLIE
    # =================================================

    if text == "callie":

        return """

# 📅 Callie

Would you like me to:

1. Check your calendar
2. Create an event
3. Review schedule
4. Something else

"""

    # =================================================
    # EMILY
    # =================================================

    if text == "emily":

        return """

# 📧 Emily

Would you like me to:

1. Check your emails
2. Summarize inbox
3. Review priorities
4. Something else

"""

    return None































































