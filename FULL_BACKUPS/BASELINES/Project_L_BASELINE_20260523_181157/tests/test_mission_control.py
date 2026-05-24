from services.runtime_mission_control_service import (
    mission_snapshot,
    mission_summary,
    mission_alerts,
    command_brief
)

print("")
print("===================================")
print("AODS 72 VALIDATION")
print("===================================")
print("")

print("MISSION SNAPSHOT:")
print(mission_snapshot())

print("")
print("MISSION SUMMARY:")
print(mission_summary())

print("")
print("MISSION ALERTS:")
print(mission_alerts())

print("")
print("COMMAND BRIEF:")
print(command_brief())
