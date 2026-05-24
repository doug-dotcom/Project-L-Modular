# ============================================================
# AUTONOMOUS ROUTING ENGINE
# AODS-98
# ============================================================

from datetime import datetime

CAPTAIN_DOMAINS = {

    "emily": [
        "email",
        "message",
        "communication",
        "reply"
    ],

    "callie": [
        "calendar",
        "appointment",
        "schedule",
        "meeting",
        "reminder"
    ],

    "fiona": [
        "finance",
        "money",
        "claim",
        "budget"
    ],

    "ellie": [
        "memory",
        "continuity",
        "identity",
        "reflection"
    ],

    "sally": [
        "safety",
        "grounding",
        "stress",
        "regulation"
    ],

    "winnie": [
        "meaning",
        "wisdom",
        "insight",
        "philosophy"
    ],

    "tegan": [
        "orchestration",
        "routing",
        "complex",
        "multi-step"
    ]
}

def route_request(user_msg):

    try:

        text = str(user_msg).lower()

        scores = {}

        for captain, triggers in CAPTAIN_DOMAINS.items():

            score = 0

            for trigger in triggers:

                if trigger in text:

                    score += 1

            scores[captain] = score

        best = max(
            scores,
            key=scores.get
        )

        if scores[best] == 0:

            best = "tegan"

        return {

            "selected_captain": best,

            "scores": scores,

            "timestamp": str(
                datetime.now()
            ),

            "operation": "AODS98"
        }

    except Exception as e:

        return {

            "selected_captain": "tegan",

            "error": str(e)
        }

def routing_status():

    return {

        "status": "online",

        "operation": "AODS98",

        "captains": list(
            CAPTAIN_DOMAINS.keys()
        )
    }
