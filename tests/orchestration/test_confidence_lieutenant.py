import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 62 CONFIDENCE LIEUTENANT TEST")
print("")

from orchestration.lieutenants.confidence_lieutenant import (
    CONFIDENCE_LIEUTENANT,
)

from memory.confidence.engine import (
    calculate_basic_confidence,
    build_memory_confidence_layer,
    confidence_status,
)

sample = [
    {
        "_retrieval_rank": 12,
        "entry": {
            "type": "identity",
            "important": True,
            "pinned": True,
        }
    }
]

assessment = CONFIDENCE_LIEUTENANT.assess_memory_confidence(sample)

if assessment.get("confidence") != "high":
    raise SystemExit("Expected high confidence")

engine_assessment = calculate_basic_confidence(sample)

if engine_assessment.get("confidence") != "high":
    raise SystemExit("Engine confidence failed")

layer = build_memory_confidence_layer(engine_assessment)

if not isinstance(layer, str):
    raise SystemExit("Confidence layer not string")

status = confidence_status()

if status.get("status") != "online":
    raise SystemExit("Confidence status offline")

print("assessment:", assessment)
print("status:", status)

print("")
print("AODS 62 CONFIDENCE LIEUTENANT ONLINE")
