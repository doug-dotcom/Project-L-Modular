# =====================================================
# orchestration_service.py
# AODS 50
# =====================================================

from datetime import datetime

class RuntimeOrchestrator:

    def __init__(self):
        self.boot_time = datetime.now().isoformat()
        self.status = "ONLINE"

    def heartbeat(self):
        return {
            "status": self.status,
            "boot_time": self.boot_time,
            "service": "Runtime Orchestrator"
        }

    def route(self, task_type):
        routes = {
            "memory": "memory_service",
            "chat": "chat_service",
            "reflection": "reflection_service",
            "identity": "identity_service"
        }

        return routes.get(task_type, "unknown")

ORCHESTRATOR = RuntimeOrchestrator()

# =====================================================
# AODS 51 — TEGAN TRIAGE BRIDGE
# =====================================================
from services.tegan_triage_service import TEGAN

def triage_message(user_message: str):
    return TEGAN.triage(user_message)

def tegan_heartbeat():
    return TEGAN.heartbeat()

# =====================================================
# AODS 60 — RECOVERY BRIDGE
# =====================================================
from services.runtime_recovery_service import recovery_summary, self_heal

def runtime_recovery_status():
    return recovery_summary()

def runtime_self_heal_now():
    return self_heal()
