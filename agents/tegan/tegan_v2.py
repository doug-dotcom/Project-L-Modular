# =====================================================
# PROJECT L - TEGAN V2 ORCHESTRATOR
# Intent-Aware Cognitive Routing
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
        "google",
        "find online",
        "check online",
        "current information",
        "current",
        "today",
        "open today",
        "closing time",
        "opening hours",
        "what time does",
        "what time is",
    ]

    return any(p in text for p in external_patterns)

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
        "my relationship",
        "what can i learn",
        "what does this mean for me",
    ]

    return any(p in text for p in personal_patterns)

# =====================================================
# INTENT CLASSIFIER
# =====================================================

def classify_intent(message: str):
    text = normalize(message)

    try:
        if emily.should_handle(text):
            return {
                "intent": "email",
                "confidence": 0.95,
                "reason": "Email request detected"
            }

        if callie.should_handle(text):
            return {
                "intent": "calendar",
                "confidence": 0.95,
                "reason": "Calendar request detected"
            }

        if tanya.should_handle(text):
            return {
                "intent": "task",
                "confidence": 0.95,
                "reason": "Task request detected"
            }

        if fiona.should_handle(text):
            return {
                "intent": "finance",
                "confidence": 0.95,
                "reason": "Finance request detected"
            }

    except Exception:
        pass

    memory_patterns = [
        "who is",
        "who are",
        "recall",
        "remember",
        "tell me about",
        "what do you know about",
        "profile",
        "my family",
        "my children",
        "my kids",
        "my recovery",
        "project l",
    ]

    if any(p in text for p in memory_patterns):
        if is_external_information_request(text) and not any(
            p in text for p in [
                "my ",
                "recall",
                "remember",
                "who is",
                "who are",
                "profile",
                "project l",
            ]
        ):
            return {
                "intent": "research",
                "confidence": 0.85,
                "reason": "External information request detected"
            }

        return {
            "intent": "memory",
            "confidence": 0.90,
            "reason": "Personal recall request detected"
        }

    if is_personal_reflection(text):
        return {
            "intent": "reflection",
            "confidence": 0.90,
            "reason": "Personal reflection request detected"
        }

    if is_external_information_request(text):
        return {
            "intent": "research",
            "confidence": 0.90,
            "reason": "External information request detected"
        }

    return {
        "intent": "general",
        "confidence": 0.50,
        "reason": "No specialist route detected"
    }

# =====================================================
# LOGGING
# =====================================================

def log_route(intent_packet, route):
    try:
        print()
        print("=" * 60)
        print("TEGAN V2")
        print("=" * 60)
        print(f"INTENT: {intent_packet.get('intent')}")
        print(f"CONFIDENCE: {intent_packet.get('confidence')}")
        print(f"REASON: {intent_packet.get('reason')}")
        print(f"ROUTE: {route}")
        print("=" * 60)
        print()
    except Exception:
        pass

# =====================================================
# ROUTER
# =====================================================

def route_message(message: str):
    text = normalize(message)

    intent_packet = classify_intent(text)
    intent = intent_packet.get("intent", "general")

    # =================================================
    # MEMORY / REFLECTION / GENERAL
    # =================================================
    # Rhee is mandatory infrastructure in Server VX.
    # These routes should fall through to L Core.
    # =================================================

    if intent in ["memory", "reflection", "general"]:
        route = {
            "handled": False,
            "agent": "L Core",
            "reply": "",
            "intent": intent_packet
        }

        log_route(intent_packet, "L Core")
        return route

    # =================================================
    # EMILY
    # =================================================

    if intent == "email":
        try:
            route = {
                "handled": True,
                "agent": "Emily",
                "reply": emily.handle_email_request(message),
                "intent": intent_packet
            }

            log_route(intent_packet, "Emily")
            return route

        except Exception as e:
            route = {
                "handled": True,
                "agent": "Emily",
                "reply": f"Emily Error: {str(e)}",
                "intent": intent_packet
            }

            log_route(intent_packet, "Emily Error")
            return route

    # =================================================
    # CALLIE
    # =================================================

    if intent == "calendar":
        try:
            route = {
                "handled": True,
                "agent": "Callie",
                "reply": callie.handle_calendar_request(message),
                "intent": intent_packet
            }

            log_route(intent_packet, "Callie")
            return route

        except Exception as e:
            route = {
                "handled": True,
                "agent": "Callie",
                "reply": f"Callie Error: {str(e)}",
                "intent": intent_packet
            }

            log_route(intent_packet, "Callie Error")
            return route

    # =================================================
    # TANYA
    # =================================================

    if intent == "task":
        try:
            route = {
                "handled": True,
                "agent": "Tanya",
                "reply": tanya.handle_task_request(message),
                "intent": intent_packet
            }

            log_route(intent_packet, "Tanya")
            return route

        except Exception as e:
            route = {
                "handled": True,
                "agent": "Tanya",
                "reply": f"Tanya Error: {str(e)}",
                "intent": intent_packet
            }

            log_route(intent_packet, "Tanya Error")
            return route

    # =================================================
    # FIONA
    # =================================================

    if intent == "finance":
        try:
            route = {
                "handled": True,
                "agent": "Fiona",
                "reply": fiona.handle_finance_request(message),
                "intent": intent_packet
            }

            log_route(intent_packet, "Fiona")
            return route

        except Exception as e:
            route = {
                "handled": True,
                "agent": "Fiona",
                "reply": f"Fiona Error: {str(e)}",
                "intent": intent_packet
            }

            log_route(intent_packet, "Fiona Error")
            return route

    # =================================================
    # BRITTANY
    # =================================================

    if intent == "research":
        try:
            route = {
                "handled": True,
                "agent": "Brittany",
                "reply": brittany.investigate(message),
                "intent": intent_packet
            }

            log_route(intent_packet, "Brittany")
            return route

        except Exception as e:
            route = {
                "handled": True,
                "agent": "Brittany",
                "reply": f"Brittany Error: {str(e)}",
                "intent": intent_packet
            }

            log_route(intent_packet, "Brittany Error")
            return route

    # =================================================
    # L CORE FALLBACK
    # =================================================

    route = {
        "handled": False,
        "agent": "L Core",
        "reply": "",
        "intent": intent_packet
    }

    log_route(intent_packet, "L Core")
    return route

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":
    tests = [
        "Who is Cass?",
        "What time does Petbarn close?",
        "Draft an email to Alan.",
        "Book lunch with Neil.",
        "Remind me to call Zurich.",
        "What can I learn from my recovery journey?",
    ]

    for test in tests:
        print(route_message(test))
