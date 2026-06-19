from supabase import create_client
from dotenv import load_dotenv

import os
import json
from pathlib import Path

# =====================================================
# RHEE V3
# MEMORY OUT ENGINE
# =====================================================

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# TABLES
# =====================================================

LONG_TERM_TABLES = [
    "memory_family",
    "memory_identity",
    "memory_relationships",
    "memory_recovery",
    "memory_health",
    "memory_project_l",
    "memory_general",
    "memory_sport",
    "memory_work",
    "memory_research",
    "episodic_memories",
    "identity_anchors",
]

SHORT_TERM_TABLES = {
    "family": "short_term_family",
    "finance": "short_term_finance",
    "general": "short_term_general",
    "health": "short_term_health",
    "identity": "short_term_identity",
    "knowledge": "short_term_knowledge",
    "project_l": "short_term_project_l",
    "recovery": "short_term_recovery",
    "relationships": "short_term_relationships",
    "sport": "short_term_sport",
    "work": "short_term_work",
}

LEARNING_TABLES = [
    "system_memory",
    "structured_summaries",
    "allegra_history",
]

# =====================================================
# SAFE HELPERS
# =====================================================

def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def safe_list(value):
    if isinstance(value, list):
        return value

    if value is None:
        return []

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return [value]

    return []


def row_content(row):
    if not isinstance(row, dict):
        return safe_text(row)

    for key in [
        "content",
        "summary",
        "learning",
        "message",
        "text",
        "anchor",
        "value",
        "description",
        "title",
    ]:
        value = safe_text(row.get(key))
        if value:
            return value

    return safe_text(row)

# =====================================================
# IDENTITY
# =====================================================

def load_identity(limit_count=25):
    lines = []

    identity_file = ROOT / "memory" / "identity_core" / "l_identity.json"

    try:
        if identity_file.exists():
            with open(identity_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            lines.append("L IDENTITY CORE")
            lines.append(f"Core Philosophy: {data.get('core_philosophy', '')}")
            lines.append(f"Communication Style: {data.get('communication_style', [])}")
            lines.append(f"Identity Anchors: {data.get('identity_anchors', [])}")
            lines.append(f"Purpose: {data.get('purpose', [])}")
            lines.append("")

    except Exception as e:
        lines.append(f"L IDENTITY LOAD ERROR: {e}")

    try:
        if supabase:
            result = (
                supabase.table("identity_anchors")
                .select("*")
                .order("id", desc=True)
                .limit(limit_count)
                .execute()
            )

            rows = result.data or []
            rows.reverse()

            if rows:
                lines.append("IDENTITY ANCHORS")

                for row in rows:
                    content = row_content(row)
                    if content:
                        lines.append(f"- {content[:500]}")

    except Exception as e:
        lines.append(f"IDENTITY ANCHORS ERROR: {e}")

    return "\n".join(lines)

# =====================================================
# LEARNINGS
# =====================================================

def load_learnings(limit_count=20):
    if not supabase:
        return ""

    lines = []

    for table_name in LEARNING_TABLES:
        try:
            result = (
                supabase.table(table_name)
                .select("*")
                .order("id", desc=True)
                .limit(limit_count)
                .execute()
            )

            rows = result.data or []
            rows.reverse()

            if not rows:
                continue

            lines.append("")
            lines.append(table_name.upper())

            for row in rows:
                content = row_content(row)
                if content:
                    lines.append(f"- {content[:500]}")

        except Exception:
            continue

    return "\n".join(lines).strip()

# =====================================================
# CONTINUITY
# =====================================================

def load_continuity(limit_count=20):
    try:
        if not supabase:
            return ""

        result = (
            supabase.table("raw_catchall")
            .select("*")
            .order("id", desc=True)
            .limit(limit_count)
            .execute()
        )

        rows = result.data or []
        rows.reverse()

        lines = []

        for row in rows:
            role = safe_text(row.get("role", "unknown")).upper()
            content = safe_text(row.get("content", ""))

            if content:
                lines.append(f"{role}: {content}")

        return "\n".join(lines)

    except Exception as e:
        return f"CONTINUITY ERROR: {e}"

# =====================================================
# SHORT TERM
# =====================================================

def classify_short_term_domain(user_message):
    try:
        from memory.classifier.short_term_classifier import classify_message

        result = safe_text(classify_message(user_message))

        if result.startswith("short_term_"):
            return result

        return SHORT_TERM_TABLES.get(result, "short_term_general")

    except Exception:
        return "short_term_general"


def load_short_term(user_message, limit_count=20):
    table_name = classify_short_term_domain(user_message)

    try:
        if not supabase:
            return "", table_name

        result = (
            supabase.table(table_name)
            .select("*")
            .order("id", desc=True)
            .limit(limit_count)
            .execute()
        )

        rows = result.data or []
        rows.reverse()

        lines = []

        for row in rows:
            role = safe_text(row.get("role", "memory")).upper()
            content = row_content(row)

            if content:
                lines.append(f"{role}: {content}")

        return "\n".join(lines), table_name

    except Exception as e:
        return f"SHORT TERM ERROR [{table_name}]: {e}", table_name

# =====================================================
# RECALL DETECTION
# =====================================================

def recall_requested(user_message):
    text = safe_text(user_message).lower()

    return (
        "recall" in text
        or "remember" in text
    )

# =====================================================
# SCORING - RHEE V2 PRESERVED
# =====================================================

def calculate_memory_score(memory, query=""):
    score = 0

    query_lower = safe_text(query).lower()
    content_lower = safe_text(memory.get("content", "")).lower()
    primary_subject = safe_text(memory.get("primary_subject", "")).lower()

    score += safe_int(memory.get("importance", 0))
    score += safe_int(memory.get("salience", 0))

    if memory.get("anchor", False):
        score += 75

    if query_lower and primary_subject and query_lower in primary_subject:
        score += 100

    for subject in safe_list(memory.get("subjects", [])):
        subject_lower = safe_text(subject).lower()
        if query_lower and subject_lower and query_lower in subject_lower:
            score += 50

    for relationship in safe_list(memory.get("relationships", [])):
        relationship_lower = safe_text(relationship).lower()
        if query_lower and relationship_lower and query_lower in relationship_lower:
            score += 40

    values = safe_list(memory.get("values", []))
    score += len(values) * 5

    for value in values:
        value_lower = safe_text(value).lower()
        if query_lower and value_lower and query_lower in value_lower:
            score += 30

    patterns = safe_list(memory.get("patterns", []))
    score += len(patterns) * 10

    for pattern in patterns:
        pattern_lower = safe_text(pattern).lower()
        if query_lower and pattern_lower and query_lower in pattern_lower:
            score += 35

    if query_lower and content_lower and query_lower in content_lower:
        score += 25

    return score

# =====================================================
# LONG TERM LOADER - RHEE V2 PRESERVED
# =====================================================

def load_table_memories(table_name, batch_size=1000):
    table_memories = []
    offset = 0

    if not supabase:
        return table_memories

    while True:
        response = (
            supabase
            .table(table_name)
            .select("*")
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        table_memories.extend(batch)

        if len(batch) < batch_size:
            break

        offset += batch_size

    return table_memories


def load_all_memories():
    memories = []

    for table_name in LONG_TERM_TABLES:
        try:
            table_memories = load_table_memories(table_name)

            for memory in table_memories:
                memory["_table"] = table_name
                memories.append(memory)

        except Exception as e:
            print(f"{table_name}: FAILED")
            print(e)

    return memories

# =====================================================
# RECALL PACKET - RHEE V2 PRESERVED
# =====================================================

def build_recall_packet(query, limit=25):
    memories = load_all_memories()
    packet = []

    for memory in memories:
        score = calculate_memory_score(memory, query)

        if score <= 0:
            continue

        memory["_score"] = score
        packet.append(memory)

    packet.sort(
        key=lambda x: x.get("_score", 0),
        reverse=True
    )

    return packet[:limit]


def format_recall_packet(query, limit=25):
    packet = build_recall_packet(query, limit)

    lines = []

    lines.append("RHEE LONG TERM RECALL PACKET")
    lines.append(f"QUERY: {query}")
    lines.append(f"MEMORIES FOUND: {len(packet)}")
    lines.append("")

    for memory in packet:
        lines.append(
            f"{memory.get('_score')} | "
            f"{memory.get('_table')} | "
            f"{memory.get('primary_subject')}"
        )

        content = row_content(memory)

        if content:
            lines.append(content[:500])

        lines.append("")

    return "\n".join(lines)

# =====================================================
# MEMORY OUT CONTEXT
# =====================================================

def build_context(user_message):
    identity_context = load_identity()
    learnings_context = load_learnings()
    continuity_context = load_continuity()
    short_term_context, short_term_domain = load_short_term(user_message)

    recall_active = recall_requested(user_message)
    long_term_context = ""

    if recall_active:
        long_term_context = format_recall_packet(user_message, limit=25)

    sections = []

    sections.append("RHEE V3 MEMORY CONTEXT")
    sections.append("")
    sections.append(f"SHORT TERM DOMAIN: {short_term_domain}")
    sections.append(f"LONG TERM RECALL ACTIVE: {recall_active}")
    sections.append("")

    sections.append("====================================================")
    sections.append("IDENTITY")
    sections.append("====================================================")
    sections.append(identity_context or "No identity context loaded.")
    sections.append("")

    sections.append("====================================================")
    sections.append("LEARNINGS")
    sections.append("====================================================")
    sections.append(learnings_context or "No learnings context loaded.")
    sections.append("")

    sections.append("====================================================")
    sections.append("CONVERSATION CONTINUITY")
    sections.append("====================================================")
    sections.append(continuity_context or "No continuity context loaded.")
    sections.append("")

    sections.append("====================================================")
    sections.append("SHORT TERM MEMORY")
    sections.append("====================================================")
    sections.append(short_term_context or "No short term context loaded.")
    sections.append("")

    if recall_active:
        sections.append("====================================================")
        sections.append("LONG TERM MEMORY")
        sections.append("====================================================")
        sections.append(long_term_context or "No long term context found.")
        sections.append("")

    return "\n".join(sections)

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("RHEE V3 ONLINE")
    print("=" * 60)

    print()
    print("=" * 60)
    print("TEST 1: FRONT OF STORE")
    print("=" * 60)
    print(build_context("How is Luella?")[:4000])

    print()
    print("=" * 60)
    print("TEST 2: RECALL WAREHOUSE")
    print("=" * 60)
    print(build_context("Recall Luella")[:4000])
