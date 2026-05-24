import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.captains.communications.captain_emily import (
    CaptainEmily
)

def test_should(msg):
    return "email" in msg.lower()

def test_execute(msg):
    return {
        "reply": "Captain Emily executed."
    }

captain = CaptainEmily(
    test_should,
    test_execute
)

print("")
print(captain)

print("")
print(captain.status())

print("")
print(captain.should_handle(
    "check my email"
))

print("")
print(captain.execute(
    "check my email"
))

print("")
print("COMMUNICATIONS DEPLOYMENT ONLINE")
