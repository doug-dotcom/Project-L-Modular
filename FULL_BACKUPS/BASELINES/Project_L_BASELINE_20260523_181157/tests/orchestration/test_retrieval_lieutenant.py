import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 61 RETRIEVAL LIEUTENANT TEST")
print("")

from orchestration.lieutenants.retrieval_lieutenant import (
    RETRIEVAL_LIEUTENANT
)

sample = [
    {
        "_score": 2,
        "entry": {
            "type": "identity",
            "important": True
        }
    },
    {
        "_score": 5,
        "entry": {
            "type": "general"
        }
    }
]

processed = (
    RETRIEVAL_LIEUTENANT
    .process_retrieval(sample)
)

if len(processed) != 2:
    raise SystemExit(
        "Lieutenant processing failed"
    )

top = processed[0]

print("top score:", top["_retrieval_rank"])

status = (
    RETRIEVAL_LIEUTENANT
    .runtime_status()
)

print("status:", status)

print("")
print("AODS 61 RETRIEVAL LIEUTENANT ONLINE")
