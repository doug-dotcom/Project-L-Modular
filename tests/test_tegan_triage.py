from services.tegan_triage_service import TEGAN

tests = [
    "remember this for later",
    "send an email to Lyndal",
    "add my appointment to calendar",
    "I feel tired and overwhelmed",
    "AODS 52 go",
    "hello L"
]

print("TEGAN HEARTBEAT:")
print(TEGAN.heartbeat())
print("")

for t in tests:
    print("INPUT:", t)
    print("TRIAGE:", TEGAN.triage(t))
    print("")
