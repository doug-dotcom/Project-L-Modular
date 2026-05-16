import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

RESULTS = []

# =====================================================
# HELPER
# =====================================================

def check(name, condition, ok_msg, fail_msg):

    if condition:

        RESULTS.append({
            "name": name,
            "status": "PASS",
            "message": ok_msg
        })

    else:

        RESULTS.append({
            "name": name,
            "status": "FAIL",
            "message": fail_msg
        })

# =====================================================
# ENV
# =====================================================

ENV_PATH = ROOT / ".env"

check(
    ".env exists",
    ENV_PATH.exists(),
    ".env found",
    ".env missing"
)

# =====================================================
# LOAD ENV
# =====================================================

try:

    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)

    dotenv_ok = True

except Exception as e:

    dotenv_ok = False

check(
    "dotenv import",
    dotenv_ok,
    "dotenv loaded",
    "dotenv failed"
)

# =====================================================
# OPENAI KEY
# =====================================================

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

check(
    "OPENAI_API_KEY",
    len(OPENAI_KEY) > 20,
    "OpenAI key present",
    "OpenAI key missing"
)

# =====================================================
# MEMORY FILES
# =====================================================

MEMORY_DIR = ROOT / "memory"

memory_files = [
    "identity.json",
    "episodic.json",
    "emotional.json",
    "structured.json",
    "session.json"
]

for file in memory_files:

    path = MEMORY_DIR / file

    check(
        file,
        path.exists(),
        f"{file} exists",
        f"{file} missing"
    )

# =====================================================
# JSON VALIDATION
# =====================================================

for file in memory_files:

    path = MEMORY_DIR / file

    try:

        with open(path, "r", encoding="utf-8") as f:
            json.load(f)

        ok = True

    except:
        ok = False

    check(
        f"{file} valid JSON",
        ok,
        f"{file} valid",
        f"{file} corrupted"
    )

# =====================================================
# MEMORY ENGINE IMPORT
# =====================================================

try:

    from core.memory_engine import (
        memory_stats,
        build_memory_context
    )

    stats = memory_stats()

    memory_ok = True

except Exception as e:

    memory_ok = False

check(
    "memory_engine",
    memory_ok,
    "memory engine import OK",
    "memory engine failed"
)

# =====================================================
# SERVER IMPORT
# =====================================================

try:

    from api.server import app

    server_ok = True

except Exception as e:

    server_ok = False

check(
    "server import",
    server_ok,
    "server import OK",
    "server import failed"
)

# =====================================================
# OPENAI IMPORT
# =====================================================

try:

    from openai import OpenAI

    openai_ok = True

except:

    openai_ok = False

check(
    "openai package",
    openai_ok,
    "openai installed",
    "openai missing"
)

# =====================================================
# UVICORN IMPORT
# =====================================================

try:

    import uvicorn

    uvicorn_ok = True

except:

    uvicorn_ok = False

check(
    "uvicorn package",
    uvicorn_ok,
    "uvicorn installed",
    "uvicorn missing"
)

# =====================================================
# RESULTS
# =====================================================

print("")
print("===================================")
print("PROJECT L VALIDATION REPORT")
print("===================================")
print("")

fails = 0

for result in RESULTS:

    status = result["status"]

    if status == "PASS":

        icon = "[PASS]"

    else:

        icon = "[FAIL]"

        fails += 1

    print(f"{icon} {result['name']}")
    print(f"       {result['message']}")
    print("")

print("===================================")

if fails == 0:

    print("ALL VALIDATION CHECKS PASSED")

else:

    print(f"{fails} VALIDATION ISSUES DETECTED")

print("===================================")
print("")
