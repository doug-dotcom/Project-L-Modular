import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
