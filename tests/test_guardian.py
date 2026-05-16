from services.guardian_service import (
    guardian_status,
    watchdog_cycle
)

print("")
print("===================================")
print("AODS 61 VALIDATION")
print("===================================")
print("")

print("INITIAL GUARDIAN STATUS:")
print(guardian_status())

print("")
print("WATCHDOG CYCLE:")
print(watchdog_cycle())

print("")
print("FINAL GUARDIAN STATUS:")
print(guardian_status())
