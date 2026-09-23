"""Layer 93: recognise supplied daily updates, conservatively, without an LLM.

Only a substantive current update with no request signals qualifies. Ambiguous
turns retain normal retrieval. This controls reading, never intake or persistence.
"""
import re


def self_contained_current_update(message: str, *, daily_only: bool = False) -> bool:
    text = str(message or "").lower().replace("’", "'")
    opening = re.sub(r"^(?:hi|hey|hello)\s+(?:l|ellie)[,.!\s]*", "", text.strip())
    daily_label = bool(re.match(
        r"(?:here(?:'s| is)\s+my\s+daily\s+(?:summary|update)|"
        r"my\s+daily\s+(?:summary|update)|daily\s+(?:summary|update))\b", opening
    ))
    current_label = bool(re.match(
        r"(?:here(?:'s| is)\s+my\s+|my\s+)?(?:morning|evening|today's)\s+"
        r"(?:summary|update)\b|(?:quick\s+)?update\s*:", opening
    ))
    # Unlabelled prose must explicitly open in the present day. Short mood
    # cues remain eligible for associative recall under the established policy.
    current_narrative = bool(re.match(
        r"(?:today\s+i\b|this\s+(?:morning|afternoon|evening)\s+i\b|"
        r"i\s+(?:started|spent|finished)\s+(?:today|this\s+morning)\b)", opening
    ))
    if not daily_label and (daily_only or not (current_label or current_narrative)):
        return False
    if len(text.split()) < 40 or "?" in text:
        return False
    # A request anywhere in a pasted update takes priority, including one at
    # the end without a question mark. False negatives are deliberately safe:
    # they keep the established retrieval and evidence-checking route.
    if re.search(
        r"\b(?:recall|remember|compare|comparison|review|history|timeline|chronology|"
        r"retrieve|search|check|verify|look\s+up|look\s+back|remind|please|"
        r"tell\s+me|show\s+me|help\s+me|can\s+you|could\s+you|would\s+you|"
        r"should|advice|recommend|summari[sz]e|"
        r"stored\s+(?:records|memories)|supporting\s+(?:evidence|source|passage)|"
        r"record\s+id|learning\s+preferences|join\s+the\s+dots|connect\s+the\s+dots)\b", text
    ):
        return False
    if re.search(r"(?:^|[.!:\n])\s*(?:and\s+)?(?:what|when|where|who|why|how)\b", text):
        return False
    if not daily_label and re.search(
        r"\b(?:previous|previously|earlier|before|again|still|used\s+to|last\s+time|"
        r"our\s+plan|we\s+(?:discussed|decided|built)|continue|resume)\b", text
    ):
        return False
    return len(re.findall(r"\b(?:i|i'm|i've|my)\b", text)) >= 3


def self_contained_daily_update(message: str) -> bool:
    """Compatibility predicate for the original labelled daily-update route."""
    return self_contained_current_update(message, daily_only=True)
