from services.identity_service import (
    build_system_prompt,
    primary_identity,
    captain_profiles,
    captain_prompt
)

print("")
print("===================================")
print("AODS 62 VALIDATION")
print("===================================")
print("")

print("PRIMARY IDENTITY:")
print(primary_identity())

print("")
print("SYSTEM PROMPT:")
print(build_system_prompt())

print("")
print("CAPTAIN PROFILES:")
print(captain_profiles())

print("")
print("CAPTAIN BUILDER PROMPT:")
print(captain_prompt("Captain Builder"))
