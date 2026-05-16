import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 48 MEMORY TARGET STRUCTURE TEST")
print("")

from memory.runtime.bridge import runtime_status, build_context
from memory.patterns.bridge import load_memory_patterns, load_memory_outcomes
from memory.confidence.bridge import confidence_status
from memory.retrieval.bridge import retrieval_status

print("runtime:", runtime_status())
print("context type:", type(build_context()).__name__)
print("patterns type:", type(load_memory_patterns()).__name__)
print("outcomes type:", type(load_memory_outcomes()).__name__)
print("confidence:", confidence_status())
print("retrieval:", retrieval_status())

print("")
print("AODS 48 MEMORY BRIDGES ONLINE")
