from orchestration.agent_registry import (
    CAPTAIN_REGISTRY,
    get_active_captains,
    build_captain_status_report
)

print("")
print("CAPTAIN REGISTRY LOADED")
print("")

print(build_captain_status_report())
