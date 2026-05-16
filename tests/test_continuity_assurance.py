from services.runtime_continuity_service import (
    continuity_checks,
    continuity_risk,
    continuity_summary,
    continuity_brief
)

print("")
print("===================================")
print("AODS 87 VALIDATION")
print("===================================")
print("")

print("CONTINUITY CHECKS:")
print(continuity_checks())

print("")
print("CONTINUITY RISK:")
print(continuity_risk())

print("")
print("CONTINUITY SUMMARY:")
print(continuity_summary())

print("")
print("CONTINUITY BRIEF:")
print(continuity_brief())
