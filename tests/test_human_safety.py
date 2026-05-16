from services.runtime_human_safety_service import (
    human_runtime_status,
    reassurance_panel,
    overload_check,
    human_brief
)

print("")
print("===================================")
print("AODS 73 VALIDATION")
print("===================================")
print("")

print("HUMAN RUNTIME STATUS:")
print(human_runtime_status())

print("")
print("REASSURANCE PANEL:")
print(reassurance_panel())

print("")
print("OVERLOAD CHECK:")
print(overload_check())

print("")
print("HUMAN BRIEF:")
print(human_brief())
