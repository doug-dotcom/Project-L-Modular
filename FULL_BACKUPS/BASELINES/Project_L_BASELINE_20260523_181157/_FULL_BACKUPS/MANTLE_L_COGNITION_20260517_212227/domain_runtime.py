# ============================================================
# DEEP DOMAIN COGNITION RUNTIME
# AODS-104
# ============================================================

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_DIR = (
    ROOT
    / "memory"
    / "domains"
)

# ============================================================
# LOAD DOMAINS
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

            domains[file.stem] = data

        except Exception as e:

            print(
                "DOMAIN LOAD ERROR:",
                file,
                e
            )

    return domains

# ============================================================
# SEMANTIC DOMAIN DETECTION
# ============================================================

def detect_relevant_domains(user_msg):

    text = str(user_msg).lower()

    matches = set()

    DOMAIN_KEYWORDS = {

        "family": [
            "kids",
            "children",
            "family",
            "daughter",
            "son",
            "iyla",
            "ashton",
            "luella",
            "mehlia",
            "ages",
            "old",
            "grade"
        ],

        "identity": [
            "who am i",
            "about me",
            "name",
            "identity",
            "values"
        ],

        "work": [
            "work",
            "career",
            "job",
            "tpd",
            "insurance",
            "zurich",
            "claim",
            "financial"
        ],

        "health": [
            "health",
            "mental",
            "adhd",
            "doctor",
            "therapy",
            "cptsd"
        ],

        "sport": [
            "sport",
            "hockey",
            "masters",
            "fullback"
        ]
    }

    for domain, keywords in DOMAIN_KEYWORDS.items():

        for keyword in keywords:

            if keyword in text:

                matches.add(domain)

    # ========================================================
    # IMPORTANT:
    # identity + general always loaded
    # ========================================================

    matches.add("identity")
    matches.add("general")

    if not matches:

        matches.add("general")

    return list(matches)

# ============================================================
# BUILD COGNITION CONTEXT
# ============================================================

def build_domain_memory_context(user_msg):

    domains = load_domains()

    relevant_domains = detect_relevant_domains(
        user_msg
    )

    grouped = defaultdict(list)

    # ========================================================
    # LOAD DOMAIN MEMORIES
    # ========================================================

    for domain_name in relevant_domains:

        domain = domains.get(
            domain_name,
            {}
        )

        memories = domain.get(
            "memories",
            []
        )

        for mem in memories:

            try:

                content = str(
                    mem.get(
                        "content",
                        ""
                    )
                ).strip()

                importance = float(
                    mem.get(
                        "importance",
                        0
                    ) or 0
                )

                if not content:
                    continue

                grouped[domain_name].append({

                    "content": content,

                    "importance": importance
                })

            except Exception:
                pass

    # ========================================================
    # SORT BY IMPORTANCE
    # ========================================================

    for domain_name in grouped:

        grouped[domain_name].sort(

            key=lambda x: x.get(
                "importance",
                0
            ),

            reverse=True
        )

    # ========================================================
    # BUILD PROMPT CONTEXT
    # ========================================================

    context_lines = []

    for domain_name, memories in grouped.items():

        context_lines.append(
            f"[{domain_name.upper()}]"
        )

        count = 0

        for mem in memories:

            content = mem.get(
                "content",
                ""
            )

            if not content:
                continue

            context_lines.append(
                f"- {content}"
            )

            count += 1

            if count >= 40:
                break

        context_lines.append("")

    if not context_lines:

        return (
            "No cognition memory loaded."
        )

    return "\n".join(context_lines)

# ============================================================
# STATUS
# ============================================================

def cognition_runtime_status():

    domains = load_domains()

    return {

        "status": "online",

        "domain_count": len(domains),

        "domains_loaded": list(
            domains.keys()
        ),

        "operation": "AODS104"
    }
