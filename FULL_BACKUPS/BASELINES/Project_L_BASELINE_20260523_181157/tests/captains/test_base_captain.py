import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.captains.base_captain import (
    BaseCaptain
)

print("")
print("CAPTAIN BASE CLASS TEST")
print("")

class TestCaptain(BaseCaptain):

    def should_handle(
        self,
        user_msg
    ):
        return "test" in user_msg.lower()

    def execute(
        self,
        user_msg
    ):
        return {
            "reply": "Test Captain executed."
        }

captain = TestCaptain(
    name="TestCaptain",
    domain="testing"
)

print(captain)

print("")
print("STATUS:")
print(captain.status())

print("")
print("SHOULD HANDLE:")
print(captain.should_handle("this is a test"))

print("")
print("EXECUTE:")
print(captain.execute("this is a test"))

print("")
print("BASE CAPTAIN ONLINE")
