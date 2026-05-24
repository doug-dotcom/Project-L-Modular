from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from openai import OpenAI

from api.schemas import ChatRequest

from api.routes.system import (
    router as system_router
)


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














from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)





from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)

from orchestration.weighted_scoring import (
    score_cognition_domains,
    calculate_agent_confidence,
    orchestration_summary,
    build_orchestra_context,
)






from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)





from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)

from orchestration.weighted_scoring import (
    score_cognition_domains,
    calculate_agent_confidence,
    orchestration_summary,
    build_orchestra_context,
)

from orchestration.specialist_state import (
    specialist_should_route,
    specialist_complete,
)







from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)





from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)

from orchestration.weighted_scoring import (
    score_cognition_domains,
    calculate_agent_confidence,
    orchestration_summary,
    build_orchestra_context,
)






from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)





from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)



from core.prompt_builder import (
    build_system_prompt,
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization,
    suppress_assistant_tail,
    detect_completion_state,
)

from core.conversational_maturity import (
    apply_conversational_maturity,
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer,
)

from orchestration.weighted_scoring import (
    score_cognition_domains,
    calculate_agent_confidence,
    orchestration_summary,
    build_orchestra_context,
)

from orchestration.specialist_state import (
    specialist_should_route,
    specialist_complete,
)

from orchestration.meta_suppression import (
    suppress_agent_routing,
)

from orchestration.invisible_orchestra import (
    log_orchestra_event,
    compose_l_response,
)

from memory.confidence import (
    calculate_memory_confidence,
    apply_memory_confidence,
    build_memory_confidence_layer,
)

from memory.memory_audit import (
    audit_memory_event,
    build_memory_audit_report,
    hard_memory_audit_v2,
    format_hard_memory_audit_v2,
)

from memory.life_story_store import (
    detect_intent,
    search_life_story,
    save_to_life_story,
    build_profile_context,
    build_story_context,
)

from memory.conversation_store import (
    save_conversation_turn,
    build_recent_conversation_context,
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


app.include_router(system_router)

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











def detect_drift(user_text):
    text = user_text.lower()
    return any(trigger in text for trigger in DRIFT_TRIGGERS)











,
            "score": memory_score
        }
    )



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

    communications_result = try_communications_command(

        user_msg,

        WINNIE_AVAILABLE,
        winnie_should_handle,
        handle_whatsapp_request,

        CALLIE_AVAILABLE,
        callie_should_handle,
        handle_calendar_request,

        EMILY_AVAILABLE,
        emily_should_handle,
        handle_email_request,

        save_conversation_turn
    )

    if communications_result:

        return communications_result


    intelligence_result = try_intelligence_command(

        user_msg,

        MILLIE_AVAILABLE,
        millie_should_handle,
        handle_memory_request,

        RICHIE_AVAILABLE,
        richie_should_handle,
        handle_reflection_request,

        GRACIE_AVAILABLE,
        gracie_should_handle,
        handle_legacy_request,

        save_conversation_turn
    )

    if intelligence_result:

        return intelligence_result


    research_finance_result = try_research_finance_command(

        user_msg,

        FIONA_AVAILABLE,
        fiona_should_handle,
        handle_finance_request,

        NOELIE_AVAILABLE,
        noelie_should_handle,
        handle_research_request,

        BRITTANY_AVAILABLE,
        brittany_should_handle,
        brittany_investigate,

        save_conversation_turn
    )

    if research_finance_result:

        return research_finance_result



    research_finance_result = try_research_finance_command(

        user_msg,

        FIONA_AVAILABLE,
        fiona_should_handle,
        handle_finance_request,

        NOELIE_AVAILABLE,
        noelie_should_handle,
        handle_research_request,

        BRITTANY_AVAILABLE,
        brittany_should_handle,
        brittany_investigate,

        save_conversation_turn
    )

    if research_finance_result:

        return research_finance_result




    
    
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

        system_prompt = build_system_prompt(
        time_context=time_context,
        memory_context=memory_context,
        tone=tone,
        cognition_context=cognition_context,
        calm_cognition_context=calm_cognition_context,
        active_skill_layer=active_skill_layer,
    )

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































































