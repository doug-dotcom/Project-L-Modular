import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 59 CAPTAIN DEPLOYMENT TEST")
print("")

# ============================================================
# IMPORTS
# ============================================================

from orchestration.active_registry import (
    register_active_captains,
    get_active_captains,
)

from orchestration.runtime_dispatch import (
    dynamic_dispatch,
)

from orchestration.tegan_runtime import (
    MajorTeganRuntime,
)

from orchestration.captains.communications.captain_emily import (
    CaptainEmily,
)

from orchestration.captains.intelligence.captain_millie import (
    CaptainMillie,
)

from orchestration.captains.research_finance.captain_fiona import (
    CaptainFiona,
)

# ============================================================
# TEST CAPTAINS
# ============================================================

def emily_should(msg):
    return "email" in msg.lower()

def emily_execute(msg):
    return {
        "captain": "Emily",
        "reply": "Emily deployed successfully."
    }

def millie_should(msg):
    return "memory" in msg.lower()

def millie_execute(msg):
    return {
        "captain": "Millie",
        "reply": "Millie deployed successfully."
    }

def fiona_should(msg):
    return "finance" in msg.lower()

def fiona_execute(msg):
    return {
        "captain": "Fiona",
        "reply": "Fiona deployed successfully."
    }

# ============================================================
# BUILD OFFICERS
# ============================================================

emily = CaptainEmily(
    emily_should,
    emily_execute
)

millie = CaptainMillie(
    millie_should,
    millie_execute
)

fiona = CaptainFiona(
    fiona_should,
    fiona_execute
)

register_active_captains([
    emily,
    millie,
    fiona
])

# ============================================================
# ACTIVE REGISTRY
# ============================================================

captains = get_active_captains()

if len(captains) != 3:
    raise SystemExit(
        "Captain registry count incorrect"
    )

print("ACTIVE REGISTRY: OK")

# ============================================================
# DIRECT DISPATCH
# ============================================================

email_result = dynamic_dispatch(
    "check my email"
)

memory_result = dynamic_dispatch(
    "show memory"
)

finance_result = dynamic_dispatch(
    "finance report"
)

if email_result["captain"] != "Emily":
    raise SystemExit("Emily dispatch failed")

if memory_result["captain"] != "Millie":
    raise SystemExit("Millie dispatch failed")

if finance_result["captain"] != "Fiona":
    raise SystemExit("Fiona dispatch failed")

print("DYNAMIC DISPATCH: OK")

# ============================================================
# TEGAN RUNTIME
# ============================================================

tegan = MajorTeganRuntime()

tegan_email = tegan.process(
    "check my email urgently"
)

tegan_memory = tegan.process(
    "show memory audit"
)

if "deployment" not in tegan_email:
    raise SystemExit(
        "Tegan deployment missing"
    )

if "deployment" not in tegan_memory:
    raise SystemExit(
        "Tegan memory deployment missing"
    )

print("TEGAN RUNTIME: OK")

# ============================================================
# OFFICER STATUS
# ============================================================

for captain in captains:

    status = captain.status()

    required = [
        "name",
        "domain",
        "rank",
        "active"
    ]

    missing = [
        k for k in required
        if k not in status
    ]

    if missing:
        raise SystemExit(
            f"{captain.name} status missing: {missing}"
        )

print("CAPTAIN STATUS: OK")

print("")
print("AODS 59 CAPTAIN DEPLOYMENT PASSED")
