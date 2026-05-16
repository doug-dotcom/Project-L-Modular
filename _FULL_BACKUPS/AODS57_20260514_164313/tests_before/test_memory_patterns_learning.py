import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 49 PATTERN + LEARNING TEST")
print("")

from memory.patterns.store import (
    load_memory_patterns,
    load_memory_outcomes,
    pattern_status
)

from memory.learning.runtime import (
    learning_status
)

patterns = load_memory_patterns()
outcomes = load_memory_outcomes()

print("patterns type:", type(patterns).__name__)
print("outcomes type:", type(outcomes).__name__)
print("pattern status:", pattern_status())
print("learning status:", learning_status())

print("")
print("AODS 49 PATTERN + LEARNING ONLINE")
