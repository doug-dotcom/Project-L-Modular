import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 58 RUNTIME INTEGRATION TEST")
print("")

# API app import
from api.main import app
print("API MAIN: OK")

# App routes
routes = [route.path for route in app.routes]
required_routes = [
    "/health",
    "/runtime/status",
    "/compatibility/status",
    "/chat",
    "/upload",
    "/memory/audit",
    "/recall",
    "/stories",
]

missing = [r for r in required_routes if r not in routes]

if missing:
    raise SystemExit("Missing routes: " + str(missing))

print("ROUTES: OK")

# Runtime bootstrap
from orchestration.runtime_bootstrap import (
    build_runtime_stack,
    build_runtime_status,
)

stack = build_runtime_stack()
status = build_runtime_status()

if "runtime_engine" not in stack:
    raise SystemExit("runtime_engine missing")

if "tegan_runtime" not in stack:
    raise SystemExit("tegan_runtime missing")

print("RUNTIME STACK: OK")
print("RUNTIME STATUS:", status.get("status"))

# Runtime engine
from orchestration.runtime_engine import RuntimeEngine

engine = RuntimeEngine()

runtime_context = {
    "time_context": "TEST TIME",
    "tone": "calm",
    "active_skill_layer": ""
}

result = engine.process_message(
    "Doug wants to test memory and runtime",
    runtime_context
)

required_keys = [
    "system_prompt",
    "deployment",
    "memory_context",
    "cognition_context",
]

missing_keys = [k for k in required_keys if k not in result]

if missing_keys:
    raise SystemExit("Runtime result missing keys: " + str(missing_keys))

print("RUNTIME ENGINE: OK")

# Memory orchestrator
from memory.orchestrator import (
    memory_orchestration_status,
    build_memory_runtime_package,
)

memory_status = memory_orchestration_status()
memory_package = build_memory_runtime_package("Doug Shine memory")

if memory_status.get("status") != "online":
    raise SystemExit("Memory orchestrator not online")

if "context" not in memory_package:
    raise SystemExit("Memory package missing context")

print("MEMORY ORCHESTRATOR: OK")

# Tegan runtime
from orchestration.tegan_runtime import MajorTeganRuntime

tegan = MajorTeganRuntime()
tegan_result = tegan.process("check my email")

if "deployment" not in tegan_result:
    raise SystemExit("Tegan deployment missing")

print("TEGAN RUNTIME: OK")

print("")
print("AODS 58 RUNTIME INTEGRATION PASSED")
