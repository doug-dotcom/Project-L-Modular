import os
import json

from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from supabase import create_client

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parent

MEMORY_DIR = ROOT / "memory"

DOMAIN_DIR = MEMORY_DIR / "domains"

PENDING_DIR = MEMORY_DIR / "pending"

PENDING_FILE = (
    PENDING_DIR /
    "pending_memory_queue.json"
)

# =====================================================
# SUPABASE
# =====================================================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    ""
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    ""
)

# =====================================================
# DOMAIN RULES
# =====================================================

DOMAIN_RULES = {

    "family": [
        "family",
        "kids",
        "children",
        "ashton",
        "luella",
        "iyla",
        "daughter",
        "son"
    ],

    "identity": [
        "identity",
        "authenticity",
        "values",
        "perspective",
        "who i am"
    ],

    "health": [
        "health",
        "adhd",
        "ptsd",
        "sleep",
        "medication",
        "recovery",
        "mental"
    ],

    "finance": [
        "money",
        "finance",
        "mortgage",
        "debt",
        "financial"
    ],

    "relationships": [
        "relationship",
        "friend",
        "love",
        "connection",
        "lyndal"
    ],

    "sport": [
        "hockey",
        "sport",
        "training",
        "coach"
    ],

    "project_l": [
        "project l",
        "memory",
        "cognition",
        "runtime",
        "agent",
        "orchestration"
    ],

    "knowledge": [
        "philosophy",
        "learning",
        "theory",
        "perspective",
        "meaning"
    ],

    "work": [
        "army",
        "work",
        "capstone",
        "insurance",
        "tpd"
    ]
}

# =====================================================
# LOG
# =====================================================

def log(msg):

    print(
        f"{datetime.now().isoformat()} | {msg}"
    )

# =====================================================
# LOAD JSON
# =====================================================

def load_json(path):

    if not path.exists():
        return []

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, list):
                return data

            return []

    except:

        return []

# =====================================================
# SAVE JSON
# =====================================================

def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

# =====================================================
# CLASSIFIER
# =====================================================

def classify_memory(content):

    text = str(content).lower()

    scores = {}

    for domain, keywords in DOMAIN_RULES.items():

        score = 0

        for keyword in keywords:

            if keyword in text:
                score += 1

        scores[domain] = score

    best = max(
        scores,
        key=scores.get
    )

    if scores[best] == 0:
        return "general"

    return best

# =====================================================
# CLEAN MEMORY
# =====================================================

def clean_memory(memory):

    memory["cleaned"] = True

    memory["canonical"] = True

    memory["domain_verified"] = True

    return memory

# =====================================================
# SALLY PRIORITY
# =====================================================

ANCHORS = [

    "perspective provides clarity",

    "i am what i am",

    "authenticity",

    "fatherhood",

    "project l"
]

def score_memory(memory):

    content = str(
        memory.get("content", "")
    ).lower()

    priority = 5

    salience = "medium"

    anchor = False

    for term in ANCHORS:

        if term in content:

            priority = 10

            salience = "high"

            anchor = True

    memory["priority"] = priority

    memory["salience"] = salience

    memory["anchor"] = anchor

    return memory

# =====================================================
# MAIN
# =====================================================

def run_rebuild():

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    log("CONNECTED TO SUPABASE")

    rows = (
        supabase
        .table("raw_catchall")
        .select("*")
        .order("created_at", desc=False)
        .execute()
    ).data or []

    log(
        f"RAW MEMORIES: {len(rows)}"
    )

    domain_data = {}

    # =============================================
    # LOAD EXISTING DOMAINS
    # =============================================

    for file in DOMAIN_DIR.glob("*.json"):

        domain_name = file.stem

        domain_data[domain_name] = load_json(file)

    # =============================================
    # PROCESS MEMORIES
    # =============================================

    processed = 0

    for row in rows:

        content = str(
            row.get("content", "")
        )

        if not content.strip():
            continue

        domain = classify_memory(content)

        memory = {

            "id": row.get("id"),

            "role": row.get("role"),

            "content": content,

            "created_at": row.get(
                "created_at"
            )
        }

        memory = clean_memory(memory)

        memory = score_memory(memory)

        if domain not in domain_data:
            domain_data[domain] = []

        domain_data[domain].append(memory)

        processed += 1

    # =============================================
    # SAVE DOMAINS
    # =============================================

    for domain, memories in domain_data.items():

        path = DOMAIN_DIR / f"{domain}.json"

        save_json(path, memories)

        log(
            f"{domain}.json -> "
            f"{len(memories)} memories"
        )

    log(
        f"REBUILD COMPLETE | "
        f"processed={processed}"
    )

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    run_rebuild()

