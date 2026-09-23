"""Layer 93: recognise supplied daily updates, conservatively, without an LLM.

Only a labelled, substantive update with no request signals qualifies. Ambiguous
turns retain normal retrieval. This controls reading, never intake or persistence.
"""
import re


def self_contained_daily_update(message: str) -> bool:
    text = str(message or "").lower().replace("’", "'")
    opening = re.sub(r"^(?:hi|hey|hello)\s+(?:l|ellie)[,.!\s]*", "", text.strip())
    if not re.match(
        r"(?:here(?:'s| is)\s+my\s+daily\s+(?:summary|update)|"
        r"my\s+daily\s+(?:summary|update)|daily\s+(?:summary|update))\b", opening
    ):
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
    return len(re.findall(r"\b(?:i|i'm|i've|my)\b", text)) >= 3
