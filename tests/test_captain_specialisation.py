from services.captain_specialisation_service import (
    list_specialisations,
    captain_runtime_card,
    capability_check
)
from services.captain_action_service import ACTION_ENGINE

print("")
print("===================================")
print("AODS 63 VALIDATION")
print("===================================")
print("")

print("SPECIALISATIONS:")
print(list_specialisations())

print("")
print("CAPTAIN BUILDER CARD:")
print(captain_runtime_card("Captain Builder"))

print("")
print("CAPABILITY CHECK:")
print(capability_check("Captain Builder", "runtime patching"))

print("")
print("ACTION ENGINE TEST:")
print(
    ACTION_ENGINE.execute(
        "Captain Builder",
        {
            "message": "AODS validation",
            "thread_id": "aods63"
        }
    )
)
