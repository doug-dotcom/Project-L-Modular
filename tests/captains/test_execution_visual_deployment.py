import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.captains.execution_visual.captain_pixie import (
    CaptainPixie
)

def test_should(msg):
    return "image" in msg.lower()

def test_execute(msg):
    return {
        "reply": "Captain Pixie executed."
    }

captain = CaptainPixie(
    test_should,
    test_execute
)

print("")
print(captain)

print("")
print(captain.status())

print("")
print(captain.should_handle(
    "create image"
))

print("")
print(captain.execute(
    "create image"
))

print("")
print("EXECUTION + VISUAL DEPLOYMENT ONLINE")
