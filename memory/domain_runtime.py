# ============================================================
# DOMAIN COGNITION RUNTIME
# AODS-103
# ============================================================

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_DIR = (
    ROOT
    / "memory"
    / "domains"
)

# ============================================================
# LOAD ALL DOMAINS
# ============================================================

def load_domains():

    domains = {}

    if not DOMAIN_DIR.exists():
        return domains

    for file in DOMAIN_DIR.glob("*.json"):

        try:

            data = json.loads(

                file.read_text(
                    encoding="utf-8"
                )
            )

            domain_name = file.stem

            domains[domain_name] = data

        except Exception as e:

            print(
                "DOMAIN LOAD ERROR:",
                file,
                e
            )

    return domains

# ============================================================
# SIMPLE DOMAIN MATCHING
# ============================================================

def detect_relevant_domains(user_msg):

    text = str(user_msg).lower()

    matches = []

    DOMAIN_KEYWORDS = {

        "family": [
            "kids",
            "children",
            "family",
            "iyla",
            "ashton",
            "luella",
            "mehlia"
        ],

        "identity": [
            "who am i",
            "about me",
            "name",
            "values",
            "identity"
        ],

        "health": [
            "health",
            "mental",
            "doctor",
            "therapy",
            "adhd",
            "cptsd"
        ],

        "sport": [
            "hockey",
            "sport",
            "fullback",
            "masters"
        ],

        "work": [
            "tpd",
            "insurance",
            "zurich",
            "claim",
            "work"
        ]
    }

    for domain, keywords in DOMAIN_KEYWORDS.items():

        for keyword in keywords:

            if keyword in text:

                matches.append(domain)

                break

    if not matches:

        matches.append("general")

    return matches

# ============================================================
# BUILD MEMORY CONTEXT
# ============================================================

def build_domain_memory_context(user_msg):

    domains = load_domains()

    relevant_domains = detect_relevant_domains(
        user_msg
    )

    context_lines = []

    for domain_name in relevant_domains:

        domain = domains.get(
            domain_name,
            {}
        )

        memories = domain.get(
            "memories",
            []
        )

        if not memories:
            continue

        context_lines.append(
            f"[{domain_name.upper()}]"
        )

        for mem in memories[:20]:

            content = str(
                mem.get(
                    "content",
                    ""
                )
            ).strip()

            if not content:
                continue

            context_lines.append(
                f"- {content}"
            )

    if not context_lines:

        return (
            "No cognition memory available."
        )

    return "\n".join(context_lines)

# ============================================================
# STATUS
# ============================================================

def cognition_runtime_status():

    domains = load_domains()

    return {

        "status": "online",

        "domains_loaded": list(
            domains.keys()
        ),

        "domain_count": len(domains),

        "operation": "AODS103"
    }
