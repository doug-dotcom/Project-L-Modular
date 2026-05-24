from services.runtime_recovery_service import (
    recovery_scan,
    recovery_summary,
    self_heal
)

print("")
print("===================================")
print("AODS 60 VALIDATION")
print("===================================")
print("")

print("RECOVERY SCAN:")
print(recovery_scan())

print("")
print("RECOVERY SUMMARY:")
print(recovery_summary())

print("")
print("SELF HEAL:")
print(self_heal())
