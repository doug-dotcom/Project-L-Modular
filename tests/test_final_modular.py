import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("SHINE L FINAL MODULAR SMOKE TEST")
print("")

from api.main import app
from core.compatibility import compatibility_status
from memory.local_runtime import runtime_status
from orchestration.tegan_triage import build_tegan_triage_report
from orchestration.agent_registry import build_captain_status_report

print("API app import: OK")
print("Compatibility:", compatibility_status())
print("Runtime:", runtime_status())

print("")
print(build_tegan_triage_report("I need help with memory and emails"))
print("")
print(build_captain_status_report())

print("")
print("FINAL SMOKE TEST COMPLETE")
