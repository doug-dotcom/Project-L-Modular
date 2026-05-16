# =====================================================
# tegan_triage_service.py
# AODS 51
# Major Tegan Triage
# =====================================================

from datetime import datetime
from services.runtime_intent_service import dominant_intent
from services.captain_registry_service import assign_captain

class TeganTriage:

    def __init__(self):
        self.name = "Major Tegan Triage"
        self.status = "ONLINE"
        self.boot_time = datetime.now().isoformat()

    def classify(self, user_message: str):

        text = (user_message or "").lower()

        if any(word in text for word in ["remember", "save", "memory", "recall"]):
            category = "memory"
            priority = "high"

        elif any(word in text for word in ["email", "inbox", "send", "draft"]):
            category = "email"
            priority = "medium"

        elif any(word in text for word in ["calendar", "appointment", "meeting", "schedule"]):
            category = "calendar"
            priority = "medium"

        elif any(word in text for word in ["sad", "scared", "anxious", "tired", "overwhelmed", "lost"]):
            category = "care"
            priority = "high"

        elif any(word in text for word in ["build", "aods", "script", "deploy", "runtime", "server"]):
            category = "build"
            priority = "high"

        else:
            category = "general"
            priority = "normal"

        intent = dominant_intent(user_message)

        return {
            "triage_by": self.name,
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "priority": priority,
            "intent": intent,
            "status": "classified"
        }

    def route(self, category: str):

        routes = {
            "memory": "Captain Memory",
            "email": "Captain Emily",
            "calendar": "Captain Callie",
            "care": "Captain Emme",
            "build": "Captain Builder",
            "general": "L"
        }

        return routes.get(category, "L")

    def triage(self, user_message: str):

        classification = self.classify(user_message)
        assignment = assign_captain(classification["category"])

        classification["assigned_to"] = assignment["assigned_to"]
        classification["assigned_rank"] = assignment["rank"]
        classification["assigned_role"] = assignment["role"]
        classification["service_key"] = assignment["service_key"]

        return classification

    def heartbeat(self):
        return {
            "service": self.name,
            "status": self.status,
            "boot_time": self.boot_time
        }

TEGAN = TeganTriage()


