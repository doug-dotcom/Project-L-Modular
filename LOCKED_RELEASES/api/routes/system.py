from fastapi import APIRouter

from memory.memory_audit import (
    build_memory_audit_report,
    hard_memory_audit_v2,
)

router = APIRouter()


SYSTEM_STABILITY = {
    "routing_stable": True,
    "memory_observable": True,
    "identity_guard_enabled": True,
    "orchestra_mode": "invisible",
    "soft_evolution_mode": False
}


@router.get("/")
def root():

    return {
        "status": "L SERVER RUNNING",
        "version": "clean-server-v2",
        "memory": "connected",
        "cors": "enabled",
    }


@router.get("/system/stability")
def system_stability():

    return SYSTEM_STABILITY


@router.get("/memory/audit")
def memory_audit():

    return build_memory_audit_report()


@router.get("/memory/audit-v2")
def memory_audit_v2():

    return hard_memory_audit_v2()
