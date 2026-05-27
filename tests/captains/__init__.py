import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 53 SERVER ROUTE CLEANUP TEST")
print("")

from fastapi import FastAPI
from api.routes import register_routes

app = FastAPI()
register_routes(app)

routes = [route.path for route in app.routes]

print("routes:")
for route in routes:
    print("-", route)

required = [
    "/chat",
    "/upload",
    "/google/status",
    "/memory/audit",
    "/recall",
    "/stories",
    "/emily",
    "/brittany",
]

missing = [r for r in required if r not in routes]

if missing:
    raise SystemExit("Missing routes: " + str(missing))

print("")
print("ROUTE REGISTRATION ONLINE")

