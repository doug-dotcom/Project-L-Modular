"""Deterministic gate between raw conversation and durable memory.

Raw and short-term memory keep the conversation intact. This gate answers a
different question: is a row trustworthy and substantive enough to become a
long-term memory without review?
"""

import re


PERSISTENCE_PATTERNS = (
    r"^(?:please\s+)?(?:save|remember|record|store)\s+(?:this|that)\b",
    r"^(?:please\s+)?remember\s+that\b",
    r"^can you remember that\b",
    r"^(?:please\s+)?mark today\b",
    r"^(?:please\s+)?note that\b",
    r"^(?:please\s+)?add (?:this|that|it) to (?:your )?memory\b",
    r"^(?:please\s+)?lock (?:this|that|it) in\b",
    r"^i want you to (?:save|remember|record|store) (?:this|that)\b",
    r"\bplease (?:save|remember|record|store) (?:this|that|it)\b",
)

NEGATED_PERSISTENCE = re.compile(
    r"\b(?:do not|don't|dont|never)\s+(?:save|remember|record|store|add|lock)\b",
    re.IGNORECASE,
)

QUESTION_STARTERS = (
    "who ", "what ", "when ", "where ", "why ", "how ",
    "can ", "could ", "would ", "should ", "do ", "does ",
    "did ", "is ", "are ", "am ", "was ", "were ", "have ",
    "has ", "will ",
)

REQUEST_STARTERS = (
    "please ", "can you ", "could you ", "would you ", "will you ",
    "tell me ", "give me ", "show me ", "look up ", "check ",
    "run ", "fix ", "build ", "create ", "make ", "write ",
    "add ", "remove ", "audit ", "search ", "find ", "forget ", "let's ",
    "let us ",
)

GREETING_PREFIXES = (
    "hey ", "hi ", "hello ", "good morning", "good afternoon",
    "good evening", "good night", "goodnight",
)

ACKNOWLEDGEMENT_WORDS = frozenset({
    "absolutely", "awesome", "boom", "brother", "cheers", "fuck",
    "good", "great", "l", "legend", "love", "mate", "nice", "no",
    "nope", "ok", "okay", "perfect", "sister", "thanks", "thank",
    "work", "yeah", "yep", "yer", "yes", "you",
})

ASSISTANT_TRANSCRIPT_OPENING = re.compile(
    r"^(?:yes|yep|yeah|absolutely|correct|perfect)[,\s\-—]+doug\b",
    re.IGNORECASE,
)

CONVERSATIONAL_REPLY_PREFIXES = (
    "yes ", "yes,", "yes —", "yes -", "yep ", "yep,", "yep —",
    "yeah ", "yeah,", "yeah —", "absolutely ", "absolutely,",
)


def clean_content(value):
    return str(value or "").strip()


def _contains_persistence_instruction(text):
    lowered = re.sub(r"^(?:hey\s+)?l[,\s:]+", "", text.lower()).lstrip()
    return any(re.search(pattern, lowered) for pattern in PERSISTENCE_PATTERNS)


def _word_count(text):
    return len(re.findall(r"[a-z0-9']+", text.lower()))


def _is_acknowledgement_only(text):
    words = re.findall(r"[a-z0-9']+", text.lower())
    return bool(words) and len(words) <= 6 and all(
        word in ACKNOWLEDGEMENT_WORDS for word in words
    )


def evaluate_promotion(row):
    """Return a structured, explainable promotion decision for one raw row."""
    if not isinstance(row, dict):
        return {"promote": False, "reason": "invalid_row", "explicit": False}

    raw_id = row.get("id")
    role = clean_content(row.get("role")).lower()
    content = clean_content(row.get("content"))

    if raw_id is None:
        return {"promote": False, "reason": "missing_raw_id", "explicit": False}
    if role != "user":
        return {"promote": False, "reason": "untrusted_source_role", "explicit": False}
    if not content:
        return {"promote": False, "reason": "empty_content", "explicit": False}

    if NEGATED_PERSISTENCE.search(content):
        return {"promote": False, "reason": "persistence_negated", "explicit": False}

    explicit = _contains_persistence_instruction(content)
    if explicit:
        if _word_count(content) < 4:
            return {"promote": False, "reason": "empty_save_instruction", "explicit": True}
        return {"promote": True, "reason": "explicit_save_instruction", "explicit": True}

    lowered = content.lower().lstrip()

    if len(content) < 12 or _word_count(content) < 3:
        return {"promote": False, "reason": "too_short", "explicit": False}
    if ASSISTANT_TRANSCRIPT_OPENING.search(content):
        return {"promote": False, "reason": "assistant_transcript", "explicit": False}
    if any(lowered.startswith(prefix) for prefix in CONVERSATIONAL_REPLY_PREFIXES):
        return {"promote": False, "reason": "conversational_reply", "explicit": False}
    if "?" in content or any(lowered.startswith(starter) for starter in QUESTION_STARTERS):
        return {"promote": False, "reason": "question_or_recall", "explicit": False}
    if _is_acknowledgement_only(content):
        return {"promote": False, "reason": "acknowledgement", "explicit": False}
    if any(lowered.startswith(prefix) for prefix in GREETING_PREFIXES) and _word_count(content) <= 12:
        return {"promote": False, "reason": "greeting", "explicit": False}
    if any(lowered.startswith(starter) for starter in REQUEST_STARTERS):
        return {"promote": False, "reason": "operational_request", "explicit": False}

    return {"promote": True, "reason": "durable_statement", "explicit": False}


def should_store_memory(content):
    """Compatibility helper for callers that only have user-authored text."""
    return evaluate_promotion({"id": 0, "role": "user", "content": content})["promote"]
