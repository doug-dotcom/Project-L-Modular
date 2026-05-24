# ============================================================
# ADAPTIVE DOMAIN COGNITION RUNTIME
# AODS-111
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
            "age",
            "old",
            "grade"
        ],

        "identity": [
            "who am i",
            "about me",
            "name",
            "identity",
            "values",
            "truth",
            "continuity"
        ],

        "work": [
            "work",
            "career",
            "job",
            "tpd",
            "insurance",
            "zurich",
            "claim",
            "financial",
            "anz"
        ],

        "health": [
            "health",
            "mental",
            "adhd",
            "doctor",
            "therapy",
            "cptsd",
            "ptsd",
            "pauline",
            "terri"
        ],

        "sport": [
            "sport",
            "hockey",
            "masters",
            "fullback",
            "netball"
        ],

        "project_l": [
            "project l",
            "memory",
            "aods",
            "orchestration",
            "cognition",
            "runtime",
            "tegan",
            "emily",
            "callie",
            "tania"
        ],

        "emotional": [
            "feel",
            "emotion",
            "flat",
            "excited",
            "joy",
            "trigger",
            "sad",
            "angry",
            "lonely"
        ]
    }

    for domain, keywords in DOMAIN_KEYWORDS.items():

        for keyword in keywords:

            if keyword in text:

                matches.add(domain)

    # ========================================================
    # ALWAYS LOAD CORE CONTINUITY
    # ========================================================

    matches.add("identity")
    matches.add("family")

    if not matches:
        matches.add("general")

    return list(matches)

# ============================================================
# BUILD ADAPTIVE MEMORY CONTEXT
# ============================================================

def build_domain_memory_context(user_msg):

    domains = load_domains()

    relevant_domains = detect_relevant_domains(
        user_msg
    )

    grouped = defaultdict(list)

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

                reinforcement = float(
                    mem.get(
                        "reinforcement",
                        0
                    ) or 0
                )

                if not content:
                    continue

                cognition_score = (
                    importance
                    + reinforcement
                )

                grouped[domain_name].append({

                    "content": content,

                    "score": cognition_score
                })

            except Exception:
                pass

    # ========================================================
    # SORT MEMORIES
    # ========================================================

    for domain_name in grouped:

        grouped[domain_name].sort(

            key=lambda x: x.get(
                "score",
                0
            ),

            reverse=True
        )

    # ========================================================
    # BUILD CONTEXT
    # ========================================================

    context_lines = []

    for domain_name, memories in grouped.items():

        context_lines.append(
            f"[{domain_name.upper()}]"
        )

        added = 0

        seen = set()

        for mem in memories:

            content = str(
                mem.get(
                    "content",
                    ""
                )
            ).strip()

            if not content:
                continue

            lower = content.lower()

            if lower in seen:
                continue

            seen.add(lower)

            context_lines.append(
                f"- {content}"
            )

            added += 1

            if added >= 12:
                break

        context_lines.append("")

    if not context_lines:

        return (
            "No adaptive cognition memory loaded."
        )

    return "\n".join(context_lines)

# ============================================================
# STATUS
# ============================================================

def cognition_runtime_status():

    domains = load_domains()

    domain_stats = {}

    for name, data in domains.items():

        memories = data.get(
            "memories",
            []
        )

        domain_stats[name] = len(memories)

    return {

        "status": "online",

        "operation": "AODS-111",

        "domain_count": len(domains),

        "domains": domain_stats
    }
