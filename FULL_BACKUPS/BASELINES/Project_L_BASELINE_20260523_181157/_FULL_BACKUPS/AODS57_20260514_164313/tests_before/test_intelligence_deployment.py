import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.captains.intelligence.captain_millie import (
    CaptainMillie
)

def test_should(msg):
    return "memory" in msg.lower()

def test_execute(msg):
    return {
        "reply": "Captain Millie executed."
    }

captain = CaptainMillie(
    test_should,
    test_execute
)

print("")
print(captain)

print("")
print(captain.status())

print("")
print(captain.should_handle(
    "show my memory"
))

print("")
print(captain.execute(
    "show my memory"
))

print("")
print("INTELLIGENCE DEPLOYMENT ONLINE")
