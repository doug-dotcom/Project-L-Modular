from services.runtime_state_service import (
    runtime_status,
    runtime_heartbeat,
    update_runtime_event,
    register_agent
)

print("")
print("===================================")
print("AODS 59 VALIDATION")
print("===================================")
print("")

print("INITIAL STATE:")
print(runtime_status())

print("")
print("HEARTBEAT:")
print(runtime_heartbeat())

print("")
print("REGISTER AGENTS:")
print(register_agent("L"))
print(register_agent("Major Tegan Triage"))
print(register_agent("Captain Builder"))

print("")
print("EVENT UPDATE:")
print(update_runtime_event("aods59_validation"))

print("")
print("FINAL STATE:")
print(runtime_status())
