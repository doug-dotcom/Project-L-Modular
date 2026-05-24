from openai import OpenAI

client = OpenAI()

# =====================================================
# runtime_endpoints.py
# CANONICAL CLEAN REBUILD
# Shine_L Runtime
# =====================================================

from fastapi import APIRouter

# =====================================================
# CORE SERVICES
# =====================================================

from services.tegan_triage_service import TEGAN

from services.captain_registry_service import (
    registry_status,
    list_captains,
    assign_captain
)

from services.memory_debug_service import (
    debug_memory_context
)

from services.thread_debug_service import (
    debug_thread
)

from services.orchestration_service import (
    tegan_heartbeat
)

# =====================================================
# ROUTER
# =====================================================

router = APIRouter()

# =====================================================
# ROOT RUNTIME STATUS
# =====================================================

@router.get("/runtime/status")
def runtime_status():

    return {
        "response": "Shine_L runtime online",
        "runtime": "ONLINE",
        "status": "STABLE",
        "cognition": "ACTIVE",
        "guardian": "MONITORING",
        "mission": "CONNECTED"
    }


# =====================================================
# HEALTH
# =====================================================

@router.get("/runtime/health")
def runtime_health():

    return {
        "response": "Runtime healthy",
        "runtime": "ONLINE",
        "status": "HEALTHY",
        "cognition": "ACTIVE",
        "triage": tegan_heartbeat(),
        "registry": registry_status()
    }


# =====================================================
# CHAT / COGNITION
# =====================================================

@router.post("/runtime/chat")
def runtime_chat(payload: dict):

    user_message = payload.get("message", "")

    try:

        completion = client.chat.completions.create(

            model="gpt-4.1-mini",

            messages=[

                {
                    "role": "system",
                    "content":
                    (
                        "You are L, the Shine runtime AI. "
                        "You are calm, intelligent, grounded, "
                        "and operational."
                    )
                },

                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        reply = completion.choices[0].message.content

        return {

            "response": reply,

            "runtime": "ONLINE",

            "status": "STABLE",

            "cognition": "ACTIVE"
        }

    except Exception as exc:

        return {

            "response":
                f"Runtime cognition error: {str(exc)}",

            "runtime": "ONLINE",

            "status": "ERROR",

            "cognition": "DEGRADED"
        }


# =====================================================
# CAPTAIN REGISTRY
# =====================================================

@router.get("/runtime/captains")
def runtime_captains():

    return {
        "captains": list_captains()
    }


@router.get("/runtime/assign/{category}")
def runtime_assign(category: str):

    return assign_captain(category)


# =====================================================
# TRIAGE TEST
# =====================================================

@router.post("/runtime/triage")
def runtime_triage(payload: dict):

    user_message = payload.get("message", "")

    result = TEGAN.triage(user_message)

    return {
        "input": user_message,
        "result": result
    }


# =====================================================
# MEMORY DEBUG
# =====================================================

@router.get("/runtime/memory-context")
def runtime_memory_context():

    return debug_memory_context()


# =====================================================
# THREAD DEBUG
# =====================================================

@router.get("/runtime/thread/{thread_id}")
def runtime_thread(thread_id: str):

    return debug_thread(thread_id)


# =====================================================
# MISSION CONTROL
# =====================================================

@router.get("/runtime/mission/summary")
def runtime_mission_summary():

    return {
        "runtime": "ONLINE",
        "status": "STABLE",
        "guardian": "MONITORING",
        "cognition": "ACTIVE",
        "captains": len(list_captains())
    }


# =====================================================
# GUARDIAN STATUS
# =====================================================

@router.get("/runtime/guardian/status")
def runtime_guardian_status():

    return {
        "guardian": "ONLINE",
        "monitoring": True,
        "drift": "LOW",
        "continuity": "VALID"
    }


# =====================================================
# OPERATOR STATUS
# =====================================================

@router.get("/runtime/operator/brief")
def runtime_operator_brief():

    return {
        "runtime": "ONLINE",
        "status": "STABLE",
        "message": "Operator layer active"
    }


# =====================================================
# SEAL STATUS
# =====================================================

@router.get("/runtime/seal/status")
def runtime_seal_status():

    return {
        "project": "Shine_L",
        "stage": "Stage 3",
        "seal": "AODS 90",
        "status": "SEALED"
    }