"""Provenance resolution and trust calibration for Project L recall."""


VALID_SOURCE_ROLES = frozenset({"user", "assistant"})

LONG_TERM_ADJUSTMENTS = {
    "user": 120,
    "assistant": -40,
    "unknown": 0,
}

RAW_ADJUSTMENTS = {
    "user": 80,
    "assistant": -20,
    "unknown": 0,
}

TRUST_RANK = {
    "user": 3,
    "unknown": 2,
    "assistant": 1,
}


def normalise_source_role(value):
    role = str(value or "").strip().lower()
    return role if role in VALID_SOURCE_ROLES else "unknown"


def build_raw_role_index(rows):
    """Index raw row roles by string id so bigint/string ids both resolve."""
    index = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        raw_id = row.get("id")
        role = normalise_source_role(row.get("role"))
        if raw_id is not None and role != "unknown":
            index[str(raw_id)] = role
    return index


def annotate_memory_provenance(memory, raw_role_index=None):
    """Attach authoritative source role without changing stored database data."""
    if not isinstance(memory, dict):
        return memory

    raw_id = memory.get("raw_id")
    linked_role = "unknown"
    if raw_id is not None and raw_role_index:
        linked_role = normalise_source_role(raw_role_index.get(str(raw_id)))

    embedded_role = normalise_source_role(memory.get("role"))

    if linked_role != "unknown":
        role = linked_role
        evidence = "raw_catchall"
    elif embedded_role != "unknown":
        role = embedded_role
        evidence = "embedded_role"
    else:
        role = "unknown"
        evidence = "unlinked"

    memory["_source_role"] = role
    memory["_provenance_evidence"] = evidence
    return memory


def memory_source_role(memory):
    if not isinstance(memory, dict):
        return "unknown"
    annotated = normalise_source_role(memory.get("_source_role"))
    if annotated != "unknown":
        return annotated
    return normalise_source_role(memory.get("role"))


def provenance_adjustment(role, raw=False):
    normalised = normalise_source_role(role)
    weights = RAW_ADJUSTMENTS if raw else LONG_TERM_ADJUSTMENTS
    return weights[normalised]


def provenance_trust_rank(memory):
    return TRUST_RANK[memory_source_role(memory)]
