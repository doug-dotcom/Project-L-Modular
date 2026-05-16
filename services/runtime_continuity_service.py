# =====================================================
# runtime_continuity_service.py
# AODS 87
# =====================================================

from datetime import datetime

from services.runtime_snapshot_service import (
    snapshot_status,
    latest_snapshot
)

from services.runtime_restoration_service import (
    restoration_status
)

from services.runtime_audit_service import (
    validate_chain
)

from services.runtime_integration_spine_service import (
    spine_health
)

from services.runtime_recovery_service import (
    recovery_summary
)

def continuity_checks():

    snapshot = snapshot_status()

    restore = restoration_status()

    audit = validate_chain()

    spine = spine_health()

    recovery = recovery_summary()

    checks = {

        "snapshot_system_online": (
            snapshot.get("status") == "online"
        ),

        "audit_chain_valid": (
            audit.get("status") == "valid"
        ),

        "spine_online": (
            spine.get("status") == "online"
        ),

        "recovery_healthy": (
            recovery.get("status") == "healthy"
        ),

        "restoration_system_online": (
            restore.get("status") == "online"
        )
    }

    continuity_valid = all(
        checks.values()
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "continuity_valid": continuity_valid,

        "checks": checks,

        "snapshot_status": snapshot,

        "restoration_status": restore,

        "audit_validation": audit,

        "spine_health": spine,

        "recovery": recovery
    }

def continuity_risk():

    checks = continuity_checks()

    failed = [
        name for name, passed
        in checks.get("checks", {}).items()
        if not passed
    ]

    risk_level = (
        "low"
        if len(failed) == 0 else
        "moderate"
        if len(failed) <= 2 else
        "high"
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "risk_level": risk_level,

        "failed_checks": failed,

        "continuity_valid": checks.get(
            "continuity_valid",
            False
        )
    }

def continuity_summary():

    latest = latest_snapshot()

    risk = continuity_risk()

    return {
        "timestamp": datetime.now().isoformat(),

        "latest_snapshot": latest.get(
            "label"
        ),

        "continuity_valid": risk.get(
            "continuity_valid"
        ),

        "risk_level": risk.get(
            "risk_level"
        ),

        "status": "summary_ready"
    }

def continuity_brief():

    return {
        "timestamp": datetime.now().isoformat(),

        "checks": continuity_checks(),

        "risk": continuity_risk(),

        "summary": continuity_summary()
    }
