"""Live short-term memory writes for Project L.

This module is deliberately small and dependency-injected: the active server owns
the Supabase client, while this layer validates and records each conversation
turn in the domain Rhee already reads.
"""

from hashlib import sha256

from memory.classifier.short_term_classifier import classify_message


WRITABLE_SHORT_TERM_TABLES = frozenset({
    "short_term_family",
    "short_term_finance",
    "short_term_general",
    "short_term_health",
    "short_term_identity",
    "short_term_knowledge",
    "short_term_project_l",
    "short_term_recovery",
    "short_term_relationships",
    "short_term_sport",
})

ALLOWED_ROLES = frozenset({"user", "assistant"})


def classify_short_term_domain(content):
    """Return a known, writable short-term table for a message."""
    table_name = str(classify_message(content) or "").strip()
    if table_name not in WRITABLE_SHORT_TERM_TABLES:
        return "short_term_general"
    return table_name


def write_short_term_memory(supabase, table_name, role, content):
    """Write one live conversation turn without risking the chat request.

    The result is structured for logging and production verification. Database
    errors are returned to the caller rather than raised, because short-term
    continuity must degrade gracefully if Supabase is temporarily unavailable.
    """
    safe_table = str(table_name or "").strip()
    safe_role = str(role or "").strip().lower()
    raw_content = str(content or "")
    safe_content = raw_content.strip()

    if supabase is None:
        return {"saved": False, "table": safe_table, "reason": "supabase_unavailable"}
    if safe_table not in WRITABLE_SHORT_TERM_TABLES:
        return {"saved": False, "table": safe_table, "reason": "invalid_table"}
    if safe_role not in ALLOWED_ROLES:
        return {"saved": False, "table": safe_table, "reason": "invalid_role"}
    if not safe_content:
        return {"saved": False, "table": safe_table, "reason": "empty_content"}

    try:
        result = (
            supabase.table(safe_table)
            .insert({"role": safe_role, "content": raw_content})
            .execute()
        )
        rows = result.data or []
        row = rows[0] if rows and isinstance(rows[0], dict) else {}
        row_id = row.get("id")
        expected_sha256 = sha256(raw_content.encode("utf-8")).hexdigest()
        stored_content = row.get("content") if "content" in row else None
        stored_sha256 = (
            sha256(str(stored_content).encode("utf-8")).hexdigest()
            if stored_content is not None
            else ""
        )
        integrity = (
            "verified"
            if stored_content is not None and str(stored_content) == raw_content
            else "mismatch"
            if stored_content is not None
            else "unverified"
        )
        return {
            "saved": True,
            "table": safe_table,
            "role": safe_role,
            "id": row_id,
            "content_sha256": expected_sha256,
            "stored_content_sha256": stored_sha256,
            "integrity": integrity,
        }
    except Exception as exc:
        return {
            "saved": False,
            "table": safe_table,
            "role": safe_role,
            "reason": "write_failed",
            "error": str(exc),
        }
