from supabase import create_client
from dotenv import load_dotenv

import os
import json
import re
import time
from pathlib import Path

# =====================================================
# RHEE V3.1
# MEMORY OUT / CONTEXT ENGINE
# =====================================================

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DOMAIN_DIR = ROOT / "memory" / "domains"
MEMORY_CACHE_TTL_SECONDS = 300
RAW_CACHE_TTL_SECONDS = 60

_memory_cache = {"loaded_at": 0.0, "rows": None}
_raw_cache = {"loaded_at": 0.0, "rows": None}

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def clean_query(query):
    text = safe_text(query).lower()

    for phrase in [
        "who is",
        "who are",
        "tell me about",
        "what do you know about",
        "what can you tell me about",
        "recall",
        "remember",
        "profile",
        "history",
    ]:
        text = text.replace(phrase, "")

    return text.strip()

def query_words(query):
    cleaned = clean_query(query)
    stop_words = {
        "about", "and", "are", "can", "could", "did", "does", "for",
        "from", "has", "have", "how", "into", "its", "know", "me",
        "more", "please", "that", "the", "their", "them", "this",
        "was", "were", "what", "when", "where", "which", "who", "why",
        "with", "would", "you", "your",
    }
    return [
        word
        for word in re.findall(r"[a-z0-9']+", cleaned)
        if len(word) >= 3 and word not in stop_words
    ]

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

def load_identity(limit_count=10):
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

def load_learnings(limit_count=8):
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

def load_continuity(limit_count=1000):
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

def classify_short_term_domain(user_message):
    try:
        from memory.classifier.short_term_classifier import classify_message

        result = safe_text(classify_message(user_message))

        if result.startswith("short_term_"):
            return result

        return SHORT_TERM_TABLES.get(result, "short_term_general")

    except Exception:
        return "short_term_general"

def load_short_term(user_message, limit_count=8):
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
                lines.append(f"{role}: {content[:700]}")

        return "\n".join(lines), table_name

    except Exception as e:
        return f"SHORT TERM ERROR [{table_name}]: {e}", table_name

def recall_requested(user_message):
    text = safe_text(user_message).lower()

    triggers = [
        "recall",
        "remember",
        "who is",
        "who are",
        "tell me about",
        "what do you know about",
        "what can you tell me about",
        "profile",
        "history",
        "my family",
        "my siblings",
        "my children",
        "my kids",
        "my dad",
        "my father",
        "my mum",
        "my mother",
        "my work history",
        "my career",
        "my recovery",
        "project l",
    ]

    return any(trigger in text for trigger in triggers)

def calculate_memory_score(memory, query=""):
    score = 0

    words = query_words(query)
    content_lower = row_content(memory).lower()
    primary_subject = safe_text(memory.get("primary_subject", "")).lower()

    relevance = 0

    if memory.get("anchor", False):
        score += 75

    for word in words:
        if word in primary_subject:
            relevance += 60

        if word in content_lower:
            relevance += 30

        for subject in safe_list(memory.get("subjects", [])):
            if word in safe_text(subject).lower():
                relevance += 45

        for relationship in safe_list(memory.get("relationships", [])):
            if word in safe_text(relationship).lower():
                relevance += 35

        for value in safe_list(memory.get("values", [])):
            if word in safe_text(value).lower():
                relevance += 25

        for pattern in safe_list(memory.get("patterns", [])):
            if word in safe_text(pattern).lower():
                relevance += 30

    # Do not inject unrelated high-salience memories.  Earlier Rhee versions
    # gave every record a positive score before checking relevance, so the
    # same generic memories crowded out the subject Doug actually asked about.
    if relevance <= 0:
        return 0

    score += relevance
    score += safe_int(memory.get("importance", 0))
    score += safe_int(memory.get("salience", memory.get("salience_score", 0)))

    score += len(safe_list(memory.get("values", []))) * 3
    score += len(safe_list(memory.get("patterns", []))) * 5

    return score


def load_local_memories():
    """Load the historical domain library shipped with Project L.

    Supabase is the live store, but the May/June memory corpus still lives in
    memory/domains.  Rhee previously ignored it completely in production.
    """
    memories = []

    if not LOCAL_DOMAIN_DIR.exists():
        return memories

    for path in sorted(LOCAL_DOMAIN_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{path.name}: LOCAL MEMORY FAILED: {e}")
            continue

        if isinstance(data, dict):
            data = data.get("memories", data.get("items", []))

        if not isinstance(data, list):
            continue

        table_name = f"local_{path.stem}"
        for item in data:
            if isinstance(item, dict):
                memory = dict(item)
            else:
                memory = {"content": safe_text(item)}
            memory["_table"] = table_name
            memories.append(memory)

    return memories

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
    now = time.monotonic()
    cached_rows = _memory_cache.get("rows")
    if cached_rows is not None and now - _memory_cache["loaded_at"] < MEMORY_CACHE_TTL_SECONDS:
        return cached_rows

    memories = load_local_memories()

    for table_name in LONG_TERM_TABLES:
        try:
            table_memories = load_table_memories(table_name)

            for memory in table_memories:
                memory["_table"] = table_name
                memories.append(memory)

        except Exception as e:
            print(f"{table_name}: FAILED")
            print(e)

    # The same historical row can exist locally and in Supabase. Prefer the
    # live Supabase version while ensuring duplicates cannot consume the
    # bounded recall packet.
    deduplicated = {}
    for memory in memories:
        fingerprint = row_content(memory).strip().lower()
        if not fingerprint:
            continue
        existing = deduplicated.get(fingerprint)
        if existing is None or not safe_text(memory.get("_table")).startswith("local_"):
            deduplicated[fingerprint] = memory

    rows = list(deduplicated.values())
    _memory_cache.update({"loaded_at": now, "rows": rows})
    return rows

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


def load_all_raw_catchall(batch_size=1000):
    now = time.monotonic()
    cached_rows = _raw_cache.get("rows")
    if cached_rows is not None and now - _raw_cache["loaded_at"] < RAW_CACHE_TTL_SECONDS:
        return cached_rows

    rows = []
    offset = 0

    if not supabase:
        return rows

    while True:
        response = (
            supabase
            .table("raw_catchall")
            .select("*")
            .order("id", desc=True)
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        rows.extend(batch)

        if len(batch) < batch_size:
            break

        offset += batch_size

    _raw_cache.update({"loaded_at": now, "rows": rows})
    return rows



STOP_WORDS = {
    "please", "recall", "remember", "conversation", "conversations",
    "where", "when", "what", "who", "the", "and", "for", "with",
    "all", "every", "everything", "said", "tell", "about", "find",
    "rest", "there", "more", "list", "show", "give", "can", "you",
    "me", "my", "i"
}

def exhaustive_requested(query):
    text = safe_text(query).lower()
    return any(trigger in text for trigger in [
        "all", "every", "everything", "complete", "entire",
        "full", "whole", "list", "find the rest", "there are more"
    ])

def evidence_mode_requested(query):
    text = safe_text(query).lower()
    return any(trigger in text for trigger in [
        "all", "every", "exact", "quote", "list", "timeline",
        "chronology", "date", "time", "times", "when"
    ])

def expanded_query_terms(query):
    text = safe_text(query).lower()

    base_terms = [
        word for word in query_words(query)
        if word not in STOP_WORDS and len(word) >= 3
    ]

    terms = set(base_terms)

    phrase_map = {
        "good night": [
            "good night",
            "goodnight",
            "sleep well",
            "went to bed",
            "go to bed",
            "bedtime",
            "sleep protocol",
            "sleep duration",
            "record the time",
            "recorded the time",
        ],
        "sleep": [
            "sleep",
            "sleep well",
            "went to bed",
            "go to bed",
            "bedtime",
            "sleep protocol",
            "sleep duration",
            "good night",
            "goodnight",
            "wake",
            "woke",
        ],
        "pauline": [
            "pauline",
            "psychologist",
            "therapy",
            "session",
            "jung",
            "individuation",
            "defusion",
            "useful",
            "loved",
            "keys to doug",
        ],
        "luella": [
            "luella",
            "daughter",
            "alien",
            "braces",
            "kitten",
            "kayd",
        ],
        "project l": [
            "project l",
            "rhee",
            "memory",
            "raw catchall",
            "aods",
            "x",
            "mary",
            "rachel",
            "carol",
            "brittany",
        ],
    }

    for phrase, related in phrase_map.items():
        if phrase in text:
            for item in related:
                terms.add(item)

    return [t for t in terms if safe_text(t)]

def calculate_raw_score(row, query=""):
    score = 0
    matched = False

    terms = expanded_query_terms(query)
    direct_terms = {
        safe_text(term).lower()
        for term in query_words(query)
        if safe_text(term)
    }
    content = safe_text(row.get("content", ""))
    content_lower = content.lower()
    role = safe_text(row.get("role", "")).lower()
    source = safe_text(row.get("source", "")).lower()

    for term in terms:
        term = safe_text(term).lower()

        if not term:
            continue

        if term in content_lower:
            matched = True
            # Exact words Doug used carry far more evidentiary weight than
            # Rhee's broad subject expansions. This keeps a specific record
            # such as "Luella ... braces" above generic daughter material.
            if term in direct_terms:
                score += 220
            else:
                score += 70 if " " in term else 30

    if not matched:
        return 0

    if role == "user":
        score += 15

    if source == "chat":
        score += 5

    score += min(len(content) // 400, 10)

    return score

def build_raw_recall_packet(query, limit=40):
    rows = load_all_raw_catchall()
    scored = []
    exhaustive = exhaustive_requested(query)
    evidence_mode = evidence_mode_requested(query)

    for row in rows:
        score = calculate_raw_score(row, query)

        if score <= 0:
            continue

        row["_score"] = score
        scored.append(row)

    scored.sort(
        key=lambda x: x.get("_score", 0),
        reverse=True
    )

    selected = scored[:40] if exhaustive else scored[:limit]
    selected.reverse()

    print("=" * 60)
    print(f"RAW ROWS SEARCHED : {len(rows)}")
    print(f"RAW MATCHES FOUND : {len(scored)}")
    print(f"RAW MATCHES SENT  : {len(selected)}")
    print(f"EVIDENCE MODE     : {evidence_mode}")
    print("=" * 60)

    lines = []
    lines.append("RHEE V5 EVIDENCE MODE RAW RECALL")
    lines.append(f"QUERY: {query}")
    lines.append(f"RAW ROWS SEARCHED: {len(rows)}")
    lines.append(f"RAW MATCHES FOUND: {len(scored)}")
    lines.append(f"EXHAUSTIVE MODE: {exhaustive}")
    lines.append(f"EVIDENCE MODE: {evidence_mode}")
    lines.append(f"RAW MATCHES INJECTED: {len(selected)}")
    lines.append("")

    if evidence_mode:
        lines.append("RHEE EVIDENCE PROTOCOL")
        lines.append("The records below are retrieved evidence.")
        lines.append("Do not invent dates, times, events, or missing details.")
        lines.append("Do not merge separate records into one event.")
        lines.append("Do not reorder unless the record clearly contains a date or time.")
        lines.append("If the evidence is incomplete, say it is incomplete.")
        lines.append("When listing results, quote or closely preserve the retrieved wording.")
        lines.append("")

    seen = set()
    record_no = 1

    for row in selected:
        role = safe_text(row.get("role", "unknown")).upper()
        content = safe_text(row.get("content", ""))
        created_at = safe_text(row.get("created_at", ""))
        row_id = safe_text(row.get("id", ""))

        if not content:
            continue

        fingerprint = content[:220].lower()

        if fingerprint in seen:
            continue

        seen.add(fingerprint)

        lines.append(f"RECORD {record_no}")
        lines.append(f"ID: {row_id}")
        lines.append(f"CREATED_AT: {created_at}")
        lines.append(f"ROLE: {role}")
        lines.append(f"SCORE: {row.get('_score', 0)}")
        lines.append("CONTENT:")
        lines.append(content[:600] if evidence_mode else content[:700])
        lines.append("")
        record_no += 1

    return "\n".join(lines)


def build_context(user_message):
    identity_context = load_identity()
    learnings_context = load_learnings()
    continuity_context = build_raw_recall_packet(user_message, limit=12)
    short_term_context, short_term_domain = load_short_term(user_message)

    recall_packet = build_recall_packet(user_message, limit=12)
    recall_active = bool(recall_packet)
    long_term_context = format_memory_packet(user_message, recall_packet)

    sections = []

    sections.append("RHEE V5 MEMORY CONTEXT")
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


def format_memory_packet(query, packet):
    lines = [
        "RHEE LONG TERM RECALL PACKET",
        f"QUERY: {query}",
        f"MEMORIES FOUND: {len(packet)}",
        "",
    ]

    for memory in packet:
        lines.append(
            f"{memory.get('_score')} | "
            f"{memory.get('_table')} | "
            f"{memory.get('primary_subject', '')}"
        )
        content = row_content(memory)
        if content:
            lines.append(content[:700])
        lines.append("")

    return "\n".join(lines)

def build_context_packet(user_message):
    context = build_context(user_message)

    return {
        "engine": "rhee",
        "version": "v5.0",
        "context": context,
        "context_size": len(context),
        "recall_active": "LONG TERM RECALL ACTIVE: True" in context,
        "short_term_domain": classify_short_term_domain(user_message),
    }

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("RHEE V3.1 ONLINE")
    print("=" * 60)

    for test in [
        "How is Luella?",
        "Recall Luella",
        "Tell me about Terri Biscak",
        "Who is Steven Pampel?",
    ]:
        print()
        print("=" * 60)
        print(test)
        print("=" * 60)
        print(build_context(test)[:4000])
