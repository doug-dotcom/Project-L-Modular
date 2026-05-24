from services.captain_tool_adapter_service import (
    adapter_profiles,
    build_tool_runtime_card,
    tool_check
)
from services.captain_action_service import ACTION_ENGINE

print("")
print("===================================")
print("AODS 64 VALIDATION")
print("===================================")
print("")

print("TOOL ADAPTERS:")
print(adapter_profiles())

print("")
print("CAPTAIN BUILDER TOOL CARD:")
print(build_tool_runtime_card("Captain Builder"))

print("")
print("TOOL CHECK ALLOWED:")
print(
    tool_check(
        "Captain Builder",
        "runtime_patch"
    )
)

print("")
print("TOOL CHECK BLOCKED:")
print(
    tool_check(
        "Captain Builder",
        "memory_delete"
    )
)

print("")
print("ACTION ENGINE TEST:")
print(
    ACTION_ENGINE.execute(
        "Captain Builder",
        {
            "message": "AODS 64 validation",
            "thread_id": "aods64"
        }
    )
)
