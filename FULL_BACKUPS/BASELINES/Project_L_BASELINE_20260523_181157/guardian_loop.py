# =====================================================
# guardian_loop.py
# AODS 61
# =====================================================

from services.guardian_service import watchdog_loop

print("")
print("===================================")
print("L GUARDIAN LOOP ONLINE")
print("===================================")
print("")

while True:

    results = watchdog_loop(iterations=1)

    print(results[-1])
