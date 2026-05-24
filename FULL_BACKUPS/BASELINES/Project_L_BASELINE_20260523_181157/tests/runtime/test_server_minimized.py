import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 56 FINAL SERVER MINIMIZATION TEST")
print("")

from api.server import app

routes = [route.path for route in app.routes]

required = [
    "/health",
    "/runtime/status",
    "/compatibility/status",
]

missing = [r for r in required if r not in routes]

if missing:
    raise SystemExit("Missing routes: " + str(missing))

print("routes online:", len(routes))

for route in required:
    print("OK:", route)

print("")
print("SERVER.PY MINIMIZED")
