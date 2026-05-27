# =====================================================
# PROJECT L - TEGAN ORCHESTRATOR
# Context-Aware Cognitive Routing
# =====================================================

from agents.brittany_browser import brittany
from agents.emily import emily
from agents.callie import callie
from agents.tanya import tanya
from agents.fiona import fiona

# =====================================================
# HELPERS
# =====================================================

def normalize(message: str):

    return (message or "").strip().lower()

# =====================================================
# CONTEXT CLASSIFICATION
# =====================================================

def is_external_information_request(text):

    external_patterns = [

        "latest",
        "news",
        "research",
        "search",
        "look up",
        "find online",
        "check online",
        "current information",

        "what is",
        "tell me about"

    ]

    return any(
        p in text
        for p in external_patterns
    )

def is_personal_reflection(text):

    personal_patterns = [

        "my journey",
        "my higher self",
        "how do i feel",
        "what do you think about me",
        "my trauma",
        "my recovery",
        "my spirituality",
        "my emotions",
        "my relationship"

    ]

    return any(
        p in text
        for p in personal_patterns
    )

# =====================================================
# ROUTER
# =====================================================

def route_message(message: str):

    text = normalize(message)

    # =================================================
    # EMILY
    # =================================================

    try:

        if emily.should_handle(text):

            return {

                "handled": True,

                "agent": "Emily",

                "reply":
                    emily.handle_email_request(
                        message
                    )

            }

    except Exception as e:

        return {

            "handled": True,

            "agent": "Emily",

            "reply":
                f"Emily Error: {str(e)}"

        }

    # =================================================
    # CALLIE
    # =================================================

    try:

        if callie.should_handle(text):

            return {

                "handled": True,

                "agent": "Callie",

                "reply":
                    callie.handle_calendar_request(
                        message
                    )

            }

    except Exception as e:

        return {

            "handled": True,

            "agent": "Callie",

            "reply":
                f"Callie Error: {str(e)}"

        }

    # =================================================
    # TANYA
    # =================================================

    try:

        if tanya.should_handle(text):

            return {

                "handled": True,

                "agent": "Tanya",

                "reply":
                    tanya.handle_task_request(
                        message
                    )

            }

    except Exception as e:

        return {

            "handled": True,

            "agent": "Tanya",

            "reply":
                f"Tanya Error: {str(e)}"

        }

    # =================================================
    # FIONA
    # =================================================

    try:

        if fiona.should_handle(text):

            return {

                "handled": True,

                "agent": "Fiona",

                "reply":
                    fiona.handle_finance_request(
                        message
                    )

            }

    except Exception as e:

        return {

            "handled": True,

            "agent": "Fiona",

            "reply":
                f"Fiona Error: {str(e)}"

        }

    # =================================================
    # BRITTANY
    # =================================================

    try:

        if brittany.should_handle(text):

            # =========================================
            # PERSONAL REFLECTION OVERRIDE
            # =========================================

            if is_personal_reflection(text):

                return {

                    "handled": False,

                    "agent": "L Core",

                    "reply": ""

                }

            # =========================================
            # EXTERNAL INFO REQUEST
            # =========================================

            if is_external_information_request(text):

                return {

                    "handled": True,

                    "agent": "Brittany",

                    "reply":
                        brittany.investigate(
                            message
                        )

                }

            # =========================================
            # DEFAULT BRITTANY
            # =========================================

            return {

                "handled": True,

                "agent": "Brittany",

                "reply":
                    brittany.investigate(
                        message
                    )

            }

    except Exception as e:

        return {

            "handled": True,

            "agent": "Brittany",

            "reply":
                f"Brittany Error: {str(e)}"

        }

    # =================================================
    # L CORE FALLBACK
    # =================================================

    return {

        "handled": False,

        "agent": "L Core",

        "reply": ""

    }