# ============================================================
# RUNTIME BOOTSTRAP
# Phase 13 - Server.py Collapse
# Central runtime construction layer
# ============================================================

from orchestration.runtime_engine import (
    RuntimeEngine,
)

from orchestration.tegan_runtime import (
    MajorTeganRuntime,
)

from memory.orchestrator import (
    memory_orchestration_status,
)

from orchestration.active_registry import (
    get_active_captains,
)

from core.config import *
from core.paths import *


def build_runtime_stack():

    runtime_engine = RuntimeEngine()

    tegan_runtime = MajorTeganRuntime()

    return {
        "runtime_engine": runtime_engine,
        "tegan_runtime": tegan_runtime,
    }


def build_runtime_status():

    captains = get_active_captains()

    return {
        "status": "online",
        "phase": "server_collapse",
        "runtime_engine": "active",
        "tegan_runtime": "active",
        "captain_count": len(captains),
        "memory": memory_orchestration_status(),
    }
