# ============================================================
# UNIFIED COGNITION MEMORY ENGINE
# STAB-07
# ============================================================

import os
import json
from pathlib import Path
from collections import defaultdict

try:
    from supabase import create_client
except Exception:
    create_client = None

ROOT = Path(__file__).resolve().parents[1]

IDENTITY_FILE = ROOT / "memory" / "identity.json"

SEMANTIC_DOMAINS = {
    "family": [
        "family", "children", "kids", "child", "son", "daughter",
        "iyla", "ashton", "luella", "mehlia", "age", "ages", "old",
        "grade", "school"
    ],
    "insurance": [
        "tpd", "insurance", "zurich", "claim", "policy", "ime",
        "medical", "retired", "will", "appointment"
    ],
    "sport": [
        "sport", "hockey", "field hockey", "fullback", "masters",
        "division", "team"
    ],
    "project_l": [
        "project l", "shine", "memory", "orchestration", "runtime",
        "supabase", "captains", "tegan", "dynamic modular",
        "ai agnostic", "diagnostic", "cognition"
    ],
    "identity": [
        "name", "doug", "about me", "who am i", "values",
        "truth", "continuity", "growth", "single", "age"
    ]
}

def _supabase_client():

    try:
        if create_client is None:
            return None

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")

        if not url or not key:
            return None

        return create_client(url, key)

    except Exception:
        return None

def _load_identity():

    try:
        if not IDENTITY_FILE.exists():
            return {}

        return json.loads(
            IDENTITY_FILE.read_text(encoding="utf-8")
        )

    except Exception:
        return {}

def _identity_context():

    data = _load_identity()

    if not data:
        return ""

    lines = []

    try:
        identity = data.get("identity", {})
        family = data.get("family", {})
        projects = data.get("projects", {})
        sport = data.get("sport", {})

        if identity.get("name"):
            lines.append(f"Name: {identity.get('name')}")

        values = identity.get("core_values", [])
        if values:
            lines.append("Core values: " + ", ".join(values))

        children = family.get("children", [])
        if children:
            lines.append("Children: " + ", ".join(children))

        project_list = projects.get("primary", [])
        if project_list:
            lines.append("Projects: " + ", ".join(project_list))

        sports = sport.get("primary", [])
        if sports:
            lines.append("Sports: " + ", ".join(sports))

    except Exception:
        pass

    return "\n".join(lines)

def _expand_query(query):

    q = str(query or "").lower()

    terms = set()

    cleaned = (
        q.replace("?", " ")
         .replace(",", " ")
         .replace(".", " ")
         .replace("'", " ")
    )

    for word in cleaned.split():
        if len(word) > 2:
            terms.add(word)

    for domain, domain_terms in SEMANTIC_DOMAINS.items():
        if domain.replace("_", " ") in q:
            terms.update(domain_terms)
            terms.add(domain)

        for t in domain_terms:
            if t in q:
                terms.update(domain_terms)
                terms.add(domain)

    return list(terms)

def _fetch_supabase_rows(query, limit=30):

    sb = _supabase_client()

    if not sb:
        return []

    terms = _expand_query(query)

    rows_by_key = {}

    def add_rows(rows):
        for row in rows or []:
            content = str(row.get("content", "")).strip()

            if not content:
                continue

            clean = {
                "id": row.get("id"),
                "type": row.get("type"),
                "category": row.get("category", "memory"),
                "content": content,
                "importance": row.get("importance", row.get("rank", 0)),
                "metadata": row.get("metadata", {})
            }

            key = str(row.get("id") or content)

            rows_by_key[key] = clean

    # Category and content search.
    for term in terms[:40]:

        try:
            result = (
                sb.table("memories")
                .select("id,type,category,content,importance,metadata")
                .ilike("category", f"%{term}%")
                .limit(limit)
                .execute()
            )
            add_rows(result.data)
        except Exception:
            pass

        try:
            result = (
                sb.table("memories")
                .select("id,type,category,content,importance,metadata")
                .ilike("content", f"%{term}%")
                .limit(limit)
                .execute()
            )
            add_rows(result.data)
        except Exception:
            pass

    rows = list(rows_by_key.values())

    def score(row):

        text = (
            str(row.get("category", "")) + " " +
            str(row.get("content", ""))
        ).lower()

        s = 0

        for term in terms:
            if term and term in text:
                s += 5

        try:
            s += int(row.get("importance") or 0)
        except Exception:
            pass

        # Identity/family facts are high-value continuity anchors.
        category = str(row.get("category", "")).lower()

        if category in ["family", "identity", "health", "insurance"]:
            s += 8

        return s

    rows.sort(key=score, reverse=True)

    return rows[:limit]

def _group_rows(rows):

    grouped = defaultdict(list)

    for row in rows:
        category = str(row.get("category", "memory")).strip() or "memory"
        content = str(row.get("content", "")).strip()

        if not content:
            continue

        # Prevent vector/embedding leakage.
        if len(content) > 1200 and "[" in content and "," in content:
            continue

        if content not in grouped[category]:
            grouped[category].append(content)

    return grouped

def _format_grouped_context(grouped):

    if not grouped:
        return "No relevant Supabase memory found."

    lines = []

    preferred_order = [
        "identity",
        "family",
        "health",
        "insurance",
        "sport",
        "project",
        "project_l",
        "general",
        "memory"
    ]

    used = set()

    for category in preferred_order:

        if category in grouped:
            used.add(category)
            lines.append(f"[{category}]")

            for item in grouped[category][:10]:
                lines.append(f"- {item}")

    for category, items in grouped.items():

        if category in used:
            continue

        lines.append(f"[{category}]")

        for item in items[:8]:
            lines.append(f"- {item}")

    return "\n".join(lines)

def build_cognition_context(user_message, limit=30):

    identity = _identity_context()

    rows = _fetch_supabase_rows(
        user_message,
        limit=limit
    )

    grouped = _group_rows(rows)

    supabase_context = _format_grouped_context(grouped)

    context = f"""
IDENTITY MEMORY:
{identity if identity else "No local identity memory found."}

SUPABASE LONG-TERM MEMORY:
{supabase_context}

COGNITION RULES:
- Use identity memory as high-confidence continuity memory.
- Use Supabase long-term memory when answering personal memory questions.
- Group related facts together before answering.
- Do not expose raw vectors, embeddings, ids, or metadata.
- If Supabase contains a relevant fact, use it.
- If memory is partial, say what is known and what is unknown.
""".strip()

    return {
        "context": context,
        "identity_loaded": bool(identity),
        "supabase_rows": len(rows),
        "groups": list(grouped.keys())
    }

def cognition_status():

    return {
        "status": "online",
        "operation": "STAB-07",
        "identity_file": str(IDENTITY_FILE),
        "domains": list(SEMANTIC_DOMAINS.keys())
    }
