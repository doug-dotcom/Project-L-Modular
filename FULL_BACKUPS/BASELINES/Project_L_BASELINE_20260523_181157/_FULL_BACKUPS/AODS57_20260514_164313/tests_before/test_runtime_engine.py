import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.runtime_engine import (
    RuntimeEngine
)

engine = RuntimeEngine()

runtime_context = {
    "time_context": "TEST TIME",
    "tone": "calm",
    "active_skill_layer": ""
}

result = engine.process_message(
    "check my email",
    runtime_context
)

print("")
print("RUNTIME ENGINE ONLINE")
print("")

print(result.keys())

print("")
print("DEPLOYMENT:")
print(result["deployment"])

print("")
print("PIPELINE ACTIVE")
