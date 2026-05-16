# ============================================================
# LEGACY COMPATIBILITY LAYER
# Phase 13 - Server.py Collapse
# ============================================================

from memory.compatibility.mnemosyne import (
    build_full_memory_context,
    build_memory_runtime_package,
)

from orchestration.runtime_bootstrap import (
    build_runtime_stack,
    build_runtime_status,
)

from orchestration.active_registry import (
    get_active_captains,
)

from orchestration.runtime_dispatch import (
    dynamic_dispatch,
)

from orchestration.tegan_runtime import (
    MajorTeganRuntime,
)

from orchestration.runtime_engine import (
    RuntimeEngine,
)


def compatibility_status():

    captains = get_active_captains()

    return {
        "status": "online",
        "phase": "legacy_compatibility_isolation",
        "captain_count": len(captains),
        "memory_runtime": "memory/",
        "server_role": "compatibility_host",
    }


def build_legacy_runtime():

    stack = build_runtime_stack()

    return {
        "runtime_engine": stack["runtime_engine"],
        "tegan_runtime": stack["tegan_runtime"],
    }
