from supabase import create_client
from dotenv import load_dotenv

import os
import json
import re
import time
from pathlib import Path

from memory.identity_core.context_builder import build_identity_context
from core.cognition.learning_engine import retrieve_growth_context
from memory.retrieval.cache_state import cache_generation
from core.cognition.temporal_memory import build_temporal_packet
from memory.retrieval.provenance import (
    annotate_memory_provenance,
    build_raw_role_index,
    memory_source_role,
    provenance_adjustment,
    provenance_trust_rank,
)

# =====================================================
# RHEE V3.1
# MEMORY OUT / CONTEXT ENGINE
# =====================================================

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DOMAIN_DIR = ROOT / "memory" / "domains"
MEMORY_CACHE_TTL_SECONDS = 300
RAW_CACHE_TTL_SECONDS = 60
MAX_ATOMIC_MEMORY_CHARS = 20000

_memory_cache = {"loaded_at": 0.0, "rows": None, "generation": -1}
_raw_cache = {"loaded_at": 0.0, "rows": None, "generation": -1}
_local_memory_cache = {"rows": None}

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
        "with", "would", "you", "your", "get", "got", "off", "her",
        "hers", "him", "his", "she", "he", "they", "it", "deep",
    }
    return [
        word
        for word in re.findall(r"[a-z0-9']+", cleaned)
        if len(word) >= 3 and word not in stop_words
    ]


def term_in_text(term, text):
    """Match recall terms as words/phrases, never as arbitrary substrings."""
    words = re.findall(r"[a-z0-9']+", safe_text(term).lower())
    if not words:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b"
    return bool(re.search(pattern, safe_text(text).lower()))


def is_historical_memory_artifact(content):
    """Identify questions/failed answers written before the ingestion gate."""
    text = safe_text(content)
    lowered = text.lower()
    persistence_cues = (
        "remember", "save this", "save that", "mark today", "note that",
        "record this", "record that", "please store", "add to memory",
    )
    uncertain_phrases = (
        "do not provide an exact", "does not provide an exact",
        "currently incomplete", "information is incomplete",
        "records are incomplete", "no exact date", "no record of",
        "don't have that information", "do not have that information",
    )
    stripped = re.sub(r"^\s*l[\s,:-]+", "", lowered)
    question_or_recall = bool(re.match(
        r"^(?:deep\s+recall|recall|when|why|what|who|where|how|can|could|"
        r"do|did|does|is|are|was|were)\b",
        stripped,
    ))
    ordinary_question = (
        text.rstrip().endswith("?") or question_or_recall
    ) and not any(cue in lowered for cue in persistence_cues)
    return ordinary_question or any(phrase in lowered for phrase in uncertain_phrases)


MONTH_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)"
)


def contains_explicit_date(text):
    value = safe_text(text).lower()
    return bool(re.search(
        rf"\b(?:"
        rf"\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|"
        rf"\d{{4}}-\d{{1,2}}-\d{{1,2}}|"
        rf"\d{{1,2}}\s+{MONTH_PATTERN}\s+\d{{4}}|"
        rf"{MONTH_PATTERN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}}"
        rf")\b",
        value,
    ))


def date_requested(query):
    text = safe_text(query).lower()
    return any(term_in_text(term, text) for term in (
        "when", "date", "what day", "which day", "timeline", "chronology",
    ))


EVENT_QUERY_TERMS = {
    "break", "broke", "breakup", "broken", "ended", "end", "separated",
    "relationship", "date", "day", "time", "timeline", "chronology",
}


def focal_query_terms(query):
    return [word for word in query_words(query) if word not in EVENT_QUERY_TERMS]


def is_recall_quarantined(memory):
    """Mirror the database quarantine rules for local/full-scan fallback."""
    if not isinstance(memory, dict):
        return False

    if safe_text(memory.get("memory_status")).upper() == "QUARANTINED":
        return True

    content = row_content(memory)
    if is_historical_memory_artifact(content):
        return True

    # Large transcript/composite blobs are archives rather than atomic facts.
    # The raw record remains preserved and can be inspected independently.
    return len(content) > MAX_ATOMIC_MEMORY_CHARS

def row_content(row):
    if not isinstance(row, dict):
        return safe_text(row)

    table_name = safe_text(row.get("_table"))
    if table_name == "episodic_memories":
        event_date = safe_text(row.get("event_date"))
        summary = safe_text(row.get("summary"))
        return " — ".join(part for part in (event_date, summary) if part)
    if table_name == "identity_anchors":
        key = safe_text(row.get("key"))
        value = safe_text(row.get("value"))
        return ": ".join(part for part in (key, value) if part)

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

            identity_context = build_identity_context(data)
            if identity_context:
                lines.append(identity_context)
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
                    if safe_text(row.get("memory_status", "ACTIVE")).upper() != "ACTIVE":
                        continue
                    key = safe_text(row.get("key"))
                    value = safe_text(row.get("value"))
                    content = ": ".join(part for part in (key, value) if part)
                    if content:
                        lines.append(f"- {content[:500]}")
    except Exception as e:
        lines.append(f"IDENTITY ANCHORS ERROR: {e}")

    return "\n".join(lines)

def load_learnings(user_message="", limit_count=8):
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

    try:
        growth = retrieve_growth_context(
            query=user_message,
            limit=limit_count,
            client=supabase,
        )
        if growth:
            lines.append("")
            lines.append("ALLEGRA GROWTH PATTERNS")
            lines.extend(f"- {item}" for item in growth)
    except Exception:
        pass

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


def load_recent_conversation(limit_count=8):
    """Load bounded chronological continuity across short-term domains."""
    if not supabase:
        return ""
    try:
        result = (
            supabase.table("raw_catchall")
            .select("id,role,content,created_at")
            .order("id", desc=True)
            .limit(limit_count)
            .execute()
        )
        rows = result.data or []
        rows.reverse()
        lines = []
        for row in rows:
            role = safe_text(row.get("role", "memory")).upper()
            content = safe_text(row.get("content", ""))
            if content:
                lines.append(f"{role}: {content[:700]}")
        return "\n".join(lines)
    except Exception as error:
        return f"RECENT CONVERSATION ERROR: {error}"

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

    direct_words = set(query_words(query))
    words = expanded_query_terms(query)
    content_lower = row_content(memory).lower()
    primary_subject = safe_text(memory.get("primary_subject", "")).lower()

    if is_recall_quarantined(memory):
        return 0

    relevance = 0

    if memory.get("anchor", False):
        score += 75

    for word in words:
        direct = word in direct_words
        if word in primary_subject:
            relevance += 60 if direct else 40

        if term_in_text(word, content_lower):
            relevance += 30 if direct else 20

        for subject in safe_list(memory.get("subjects", [])):
            if word in safe_text(subject).lower():
                relevance += 45 if direct else 30

        for relationship in safe_list(memory.get("relationships", [])):
            if word in safe_text(relationship).lower():
                relevance += 35 if direct else 25

        for value in safe_list(memory.get("values", [])):
            if word in safe_text(value).lower():
                relevance += 25 if direct else 15

        for pattern in safe_list(memory.get("patterns", [])):
            if word in safe_text(pattern).lower():
                relevance += 30 if direct else 20

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
    score += provenance_adjustment(memory_source_role(memory))

    focal_terms = focal_query_terms(query)
    if (
        date_requested(query)
        and contains_explicit_date(content_lower)
        and any(term_in_text(term, content_lower) for term in focal_terms)
    ):
        score += 500

    if pauline_report_requested(query):
        # Six-month handovers need dated progress notes and Pauline/session
        # reports ahead of broad identity archives that merely share a topic.
        report_signals = (
            "pauline", "session report", "weekly report", "daily report",
            "recovery progress report", "medical report", "psychologist",
        )
        score += sum(
            90 for signal in report_signals
            if term_in_text(signal, content_lower)
        )
        if contains_explicit_date(content_lower):
            score += 120

    return score


def load_local_memories():
    """Load the historical domain library shipped with Project L.

    Supabase is the live store, but the May/June memory corpus still lives in
    memory/domains.  Rhee previously ignored it completely in production.
    """
    cached_rows = _local_memory_cache.get("rows")
    if cached_rows is not None:
        return [dict(memory) for memory in cached_rows]

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

    # This corpus ships with the application and cannot change between
    # deployments, so parsing it once per process is sufficient. Return
    # copies because recall scoring annotates rows with a transient score.
    _local_memory_cache["rows"] = memories
    return [dict(memory) for memory in memories]


def deduplicate_memories(memories):
    """Collapse duplicate content without weakening provenance ordering."""
    deduplicated = {}
    for memory in memories:
        fingerprint = row_content(memory).strip().lower()
        if not fingerprint:
            continue
        existing = deduplicated.get(fingerprint)
        candidate_rank = provenance_trust_rank(memory)
        existing_rank = provenance_trust_rank(existing) if existing else -1
        candidate_is_live = not safe_text(memory.get("_table")).startswith("local_")
        existing_is_local = bool(existing) and safe_text(existing.get("_table")).startswith("local_")
        if (
            existing is None
            or candidate_rank > existing_rank
            or (candidate_rank == existing_rank and candidate_is_live and existing_is_local)
        ):
            deduplicated[fingerprint] = memory
    return list(deduplicated.values())

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
    generation = cache_generation("long_term")
    cached_rows = _memory_cache.get("rows")
    if (
        cached_rows is not None
        and _memory_cache.get("generation") == generation
        and now - _memory_cache["loaded_at"] < MEMORY_CACHE_TTL_SECONDS
    ):
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

    # Resolve organised rows back to the role in raw_catchall. That linked
    # source is authoritative; local archives fall back to their embedded
    # user/assistant role and genuinely unlinked rows remain neutral.
    raw_role_index = build_raw_role_index(load_all_raw_catchall())
    for memory in memories:
        annotate_memory_provenance(memory, raw_role_index)

    # The same historical row can exist locally and in Supabase. Prefer the
    # more trustworthy provenance first, then the live Supabase version when
    # both copies have the same source role.
    rows = deduplicate_memories(memories)
    # Store the generation captured before loading. If a concurrent write
    # invalidated the cache mid-load, the next read will detect the mismatch
    # and refresh again rather than blessing a potentially stale snapshot.
    _memory_cache.update({"loaded_at": now, "rows": rows, "generation": generation})
    return rows

def build_recall_packet(query, limit=25, database_memories=None):
    if database_memories is None:
        memories = load_all_memories()
    else:
        memories = load_local_memories()
        for memory in memories:
            annotate_memory_provenance(memory)
        memories.extend(dict(memory) for memory in database_memories)
        memories = deduplicate_memories(memories)
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

    if pauline_report_requested(query):
        diversified = []
        per_table = {}
        for memory in packet:
            table = safe_text(memory.get("_table", "unknown"))
            if per_table.get(table, 0) >= 8:
                continue
            diversified.append(memory)
            per_table[table] = per_table.get(table, 0) + 1
            if len(diversified) >= limit:
                break
        return diversified

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
            f"{memory.get('primary_subject')} | "
            f"SOURCE_ROLE={memory_source_role(memory).upper()}"
        )

        content = row_content(memory)

        if content:
            lines.append(content[:500])

        lines.append("")

    return "\n".join(lines)


def load_all_raw_catchall(batch_size=1000):
    now = time.monotonic()
    generation = cache_generation("raw")
    cached_rows = _raw_cache.get("rows")
    if (
        cached_rows is not None
        and _raw_cache.get("generation") == generation
        and now - _raw_cache["loaded_at"] < RAW_CACHE_TTL_SECONDS
    ):
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

    _raw_cache.update({"loaded_at": now, "rows": rows, "generation": generation})
    return rows



STOP_WORDS = {
    "please", "recall", "remember", "conversation", "conversations",
    "where", "when", "what", "who", "the", "and", "for", "with",
    "all", "every", "everything", "said", "tell", "about", "find",
    "rest", "there", "more", "list", "show", "give", "can", "you",
    "me", "my", "i", "a", "an", "is", "are", "was", "were",
    "do", "does", "did", "get", "got", "off", "her", "hers",
    "him", "his", "she", "he", "they", "their", "them", "it"
}

UNCERTAIN_RECALL_PHRASES = (
    "do not provide an exact",
    "does not provide an exact",
    "currently incomplete",
    "information is incomplete",
    "records are incomplete",
    "no exact date",
    "no record of",
    "don't have that information",
    "do not have that information",
)


def pauline_report_requested(query):
    """Recognise the bounded clinical-summary workflow, not generic reports."""
    text = safe_text(query).lower()
    asks_for_report = any(term_in_text(term, text) for term in (
        "report", "summary", "six month review", "6 month review",
    ))
    pauline_context = any(term_in_text(term, text) for term in (
        "pauline", "psychologist", "therapy report",
    ))
    six_month_context = any(term_in_text(term, text) for term in (
        "last six months", "past six months", "last 6 months", "past 6 months",
    ))
    return asks_for_report and (pauline_context or six_month_context)


def deep_recall_requested(query):
    text = safe_text(query).lower()
    return term_in_text("deep recall", text) or pauline_report_requested(text)


def exhaustive_requested(query):
    text = safe_text(query).lower()
    return deep_recall_requested(query) or any(term_in_text(trigger, text) for trigger in [
        "all memories", "every memory", "everything you know", "entire memory",
        "whole memory", "complete history", "full history", "list all",
        "find the rest", "there are more",
    ])

def evidence_mode_requested(query):
    text = safe_text(query).lower()
    return deep_recall_requested(query) or any(term_in_text(trigger, text) for trigger in [
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

    if pauline_report_requested(text):
        terms.update({
            "pauline", "psychologist", "therapy", "recovery", "sobriety",
            "clean", "meeting", "step", "sponsor", "trauma", "identity",
            "family", "relationship", "health", "progress", "challenge",
            "insight", "overwhelm", "growth", "hader", "aa", "na",
        })

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
        "break up": [
            "break up", "breakup", "broke up", "broken up",
            "relationship ended", "ended relationship", "separated",
        ],
        "broke up": [
            "break up", "breakup", "broke up", "broken up",
            "relationship ended", "ended relationship", "separated",
        ],
        "breakup": [
            "break up", "breakup", "broke up", "broken up",
            "relationship ended", "ended relationship", "separated",
        ],
        "project l": [
            "project l",
            "rhee",
            "rike",
            "memory",
            "raw catchall",
            "aods",
            "mary",
            "quinn",
            "carol",
            "sara",
            "brains trust",
            "cognitive architecture",
            "provenance",
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
        if safe_text(term) and safe_text(term).lower() not in STOP_WORDS
    }
    content = safe_text(row.get("content", ""))
    content_lower = content.lower()
    role = safe_text(row.get("role", "")).lower()
    source = safe_text(row.get("source", "")).lower()

    # Raw history is never deleted, but historical questions and failed recall
    # replies must not be treated as affirmative evidence.
    if is_historical_memory_artifact(content):
        return 0

    for term in terms:
        term = safe_text(term).lower()

        if not term:
            continue

        if term_in_text(term, content_lower):
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

    # Questions and earlier failed answers are conversation artefacts, not
    # affirmative evidence. Keep them searchable but below factual records.
    if content.rstrip().endswith("?"):
        score -= 300

    if any(phrase in content_lower for phrase in UNCERTAIN_RECALL_PHRASES):
        score -= 500

    if evidence_mode_requested(query) and contains_explicit_date(content_lower):
        score += 100

    focal_terms = focal_query_terms(query)
    if (
        date_requested(query)
        and contains_explicit_date(content_lower)
        and any(term_in_text(term, content_lower) for term in focal_terms)
    ):
        score += 500

    if role == "user":
        score += provenance_adjustment(role, raw=True)
    elif role == "assistant":
        score += provenance_adjustment(role, raw=True)

    if source == "chat":
        score += 5

    score += min(len(content) // 400, 10)

    return score

def build_raw_recall_packet(query, limit=40, rows=None, evidence_out=None):
    if rows is None:
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

    selected_limit = 30 if pauline_report_requested(query) else (
        24 if deep_recall_requested(query) else (40 if exhaustive else limit)
    )
    selected = scored[:selected_limit]

    print("=" * 60)
    print(f"RAW ROWS SEARCHED : {len(rows)}")
    print(f"RAW MATCHES FOUND : {len(scored)}")
    print(f"RAW MATCHES SENT  : {len(selected)}")
    print("RAW RECORD IDS SENT: " + ",".join(
        safe_text(row.get("id")) for row in selected if row.get("id") is not None
    ))
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
        lines.append("Records are ordered highest-confidence first.")
        lines.append("Doug-authored USER records are primary evidence.")
        lines.append("ASSISTANT records are secondary and cannot override conflicting USER records.")
        lines.append("Prefer direct, affirmative, dated records over questions or uncertainty replies.")
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
        excerpt = content[:1200] if pauline_report_requested(query) else content[:600 if evidence_mode else 700]
        lines.append(excerpt)
        if evidence_out is not None and row_id:
            evidence_out.append({"source": f"raw_catchall:{row_id}", "quote_source": excerpt,
                                 "role": role.lower(), "created_at": created_at})
        lines.append("")
        record_no += 1

    return "\n".join(lines)


def database_search_terms(query):
    """Return bounded lexemes for the database candidate search."""
    terms = []
    seen = set()
    text = safe_text(query).lower()
    low_value_terms = {
        "any", "best", "compare", "created", "current", "forward",
        "identify", "now", "original", "path", "project", "supported", "tell",
    } if "project l" in text else set()
    if pauline_report_requested(text):
        low_value_terms.update({"based", "full", "last", "months", "report", "summary", "write"})

    ordered_terms = list(query_words(query))
    if pauline_report_requested(text):
        ordered_terms.extend([
            "pauline", "recovery", "therapy", "meeting", "step", "sponsor",
            "trauma", "identity", "family", "relationship", "health",
            "progress", "challenge", "overwhelm", "hader", "aa", "na",
        ])
    ordered_terms.extend(sorted(expanded_query_terms(query)))
    for expanded_term in ordered_terms:
        for token in re.findall(r"[a-z0-9]+", safe_text(expanded_term).lower()):
            if len(token) < 2 or token in seen or token in low_value_terms:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= 24:
                return terms
    return terms


def search_database_candidates(query, raw_limit=200, memory_limit=80):
    """Fetch bounded indexed candidates in one RPC, or signal fallback."""
    if not supabase:
        return None

    terms = database_search_terms(query)
    if not terms:
        return {"raw": [], "memories": []}

    def execute(candidate_raw_limit, candidate_memory_limit):
        response = supabase.rpc(
            "search_project_l_memory",
            {
                "p_terms": terms,
                "p_raw_limit": min(max(safe_int(candidate_raw_limit, 200), 1), 500),
                "p_memory_limit": min(max(safe_int(candidate_memory_limit, 80), 1), 500),
            },
        ).execute()
        payload = response.data or {}
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            payload = payload[0]
        if not isinstance(payload, dict):
            raise ValueError("candidate search returned a non-object payload")

        raw_rows = payload.get("raw", [])
        memory_rows = payload.get("memories", [])
        if not isinstance(raw_rows, list) or not isinstance(memory_rows, list):
            raise ValueError("candidate search returned malformed row lists")

        return {"raw": raw_rows, "memories": memory_rows}

    try:
        return execute(raw_limit, memory_limit)
    except Exception as error:
        print(f"INDEXED MEMORY SEARCH RETRY: {error}")
        try:
            return execute(min(safe_int(raw_limit, 200), 100), min(safe_int(memory_limit, 80), 60))
        except Exception as retry_error:
            # Deployment order and transient database errors must not take L's
            # memory offline. The caller retains the proven full-scan path.
            print(f"INDEXED MEMORY SEARCH FALLBACK: {retry_error}")
            return None


def build_context(user_message, evidence_out=None):
    identity_context = load_identity()
    learnings_context = load_learnings(user_message=user_message)
    exhaustive = exhaustive_requested(user_message)
    deep_recall = deep_recall_requested(user_message)
    pauline_report = pauline_report_requested(user_message)
    candidates = search_database_candidates(
        user_message,
        # Raw evidence contains questions and historical failed answers that
        # Python deliberately down-ranks, so retain a wider candidate pool.
        raw_limit=200 if exhaustive else 100,
        memory_limit=160 if pauline_report else (120 if exhaustive else 40),
    )
    raw_candidates = candidates["raw"] if candidates is not None else None
    memory_candidates = candidates["memories"] if candidates is not None else None

    continuity_context = build_raw_recall_packet(
        user_message,
        limit=12,
        rows=raw_candidates,
        evidence_out=evidence_out,
    )
    recent_conversation_context = load_recent_conversation()
    short_term_context, short_term_domain = load_short_term(user_message)

    recall_packet = build_recall_packet(
        user_message,
        limit=36 if pauline_report else (20 if deep_recall else 12),
        database_memories=memory_candidates,
    )
    print("LONG TERM RECORDS SENT: " + ",".join(
        f"{safe_text(memory.get('_table'))}:{safe_text(memory.get('id'))}"
        for memory in recall_packet
    ))
    recall_active = bool(recall_packet)
    long_term_context = format_memory_packet(user_message, recall_packet, evidence_out=evidence_out)

    sections = []

    sections.append("RHEE V5 MEMORY CONTEXT")
    sections.append("")
    sections.append(f"SHORT TERM DOMAIN: {short_term_domain}")
    sections.append(f"LONG TERM RECALL ACTIVE: {recall_active}")
    sections.append(f"DEEP RECALL MODE: {deep_recall}")
    sections.append(f"PAULINE REPORT MODE: {pauline_report}")
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
    sections.append("RECENT CONVERSATION")
    sections.append("====================================================")
    sections.append(recent_conversation_context or "No recent conversation loaded.")
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


def format_memory_packet(query, packet, evidence_out=None):
    lines = [
        "RHEE LONG TERM RECALL PACKET",
        f"QUERY: {query}",
        f"MEMORIES FOUND: {len(packet)}",
        "PROVENANCE: USER records are Doug-authored primary evidence; ASSISTANT records are secondary.",
        "CONFLICT RULE: A conflicting ASSISTANT record must not override a USER record.",
        "",
    ]

    for memory in packet:
        lines.append(
            f"{memory.get('_score')} | "
            f"{memory.get('_table')} | "
            f"ID={safe_text(memory.get('id'))} | "
            f"CREATED_AT={safe_text(memory.get('created_at'))} | "
            f"{memory.get('primary_subject', '')} | "
            f"SOURCE_ROLE={memory_source_role(memory).upper()} | "
            f"PROVENANCE={memory.get('_provenance_evidence', 'unlinked')}"
        )
        content = row_content(memory)
        if content:
            # Ordinary chat remains tightly bounded. A six-month clinical
            # handover needs enough of each dated report to preserve the
            # actual event and insight instead of only its introductory text.
            excerpt_limit = 1600 if pauline_report_requested(query) else 700
            excerpt = content[:excerpt_limit]
            lines.append(excerpt)
            if evidence_out is not None and memory.get("_table") and memory.get("id") is not None:
                evidence_out.append({
                    "source": f"{memory['_table']}:{memory['id']}",
                    "quote_source": excerpt, "role": memory_source_role(memory),
                    "created_at": safe_text(memory.get("created_at")),
                    "raw_id": memory.get("raw_id"),
                })
        lines.append("")

    return "\n".join(lines)

def build_context_packet(user_message):
    evidence = []
    context = build_context(user_message, evidence_out=evidence)
    temporal = build_temporal_packet(supabase, user_message)
    context += '\n\n' + temporal['context']
    evidence.extend(temporal['evidence'])

    return {
        "evidence": evidence,
        "temporal_memory": temporal['receipt'],
        "engine": "rhee",
        "version": "v5.0",
        "context": context,
        "context_size": len(context),
        "recall_active": "LONG TERM RECALL ACTIVE: True" in context,
        "deep_recall": deep_recall_requested(user_message),
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
