import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.captains.research_finance.captain_fiona import (
    CaptainFiona
)

def test_should(msg):
    return "finance" in msg.lower()

def test_execute(msg):
    return {
        "reply": "Captain Fiona executed."
    }

captain = CaptainFiona(
    test_should,
    test_execute
)

print("")
print(captain)

print("")
print(captain.status())

print("")
print(captain.should_handle(
    "help with finance"
))

print("")
print(captain.execute(
    "help with finance"
))

print("")
print("RESEARCH + FINANCE DEPLOYMENT ONLINE")

