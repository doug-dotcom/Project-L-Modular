from services.tegan_triage_service import TEGAN
from services.captain_registry_service import registry_status

print("")
print("===================================")
print("AODS 53 VALIDATION")
print("===================================")
print("")

print("REGISTRY STATUS:")
print(registry_status())
print("")

tests = [
    "remember this conversation",
    "send an email",
    "book a meeting",
    "I feel overwhelmed",
    "AODS build deploy",
    "hello L"
]

for t in tests:

    result = TEGAN.triage(t)

    print("INPUT:", t)
    print("CATEGORY:", result["category"])
    print("ASSIGNED:", result["assigned_to"])
    print("PRIORITY:", result["priority"])
    print("")
