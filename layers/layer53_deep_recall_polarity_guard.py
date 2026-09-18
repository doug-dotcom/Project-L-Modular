"""Layer 53 — Deep Recall negation / polarity fidelity guard.

Keyword retrieval can correctly find a record while composition reads its
polarity incorrectly. "I did not work at X", "that wasn't Dad", or "I never
lived there" contains the same high-value entities and verbs as the opposite
claim. Deep Recall must preserve the negation rather than turning lexical
relevance into a positive autobiographical fact.

This final composition guard flags strong negation/correction polarity in
retrieved evidence for assertion-level reading. It does not assume every "not"
negates the whole record and does not affect ordinary Recall.
"""
import re

NEGATION_RE = re.compile(
    r"\b(?:did\s+not|didn'?t|do\s+not|don'?t|was\s+not|wasn'?t|"
    r"were\s+not|weren'?t|is\s+not|isn'?t|are\s+not|aren'?t|"
    r"have\s+not|haven'?t|has\s+not|hasn'?t|had\s+not|hadn'?t|"
    r"never|no longer|not actually|not really|not me|not mine|"
    r"not my|not the|rather than|instead of)\b",
    re.I,
)

CORRECTION_POLARITY_RE = re.compile(
    r"\b(?:not\s+[^.!?\n]{1,80}\s+but\s+|"
    r"actually\s+[^.!?\n]{0,80}|"
    r"correction\s*[:—-]?\s*[^.!?\n]{0,100})",
    re.I,
)


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        flagged = []
        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            cues = []
            if NEGATION_RE.search(text):
                cues.append("negation")
            if CORRECTION_POLARITY_RE.search(text):
                cues.append("correction_polarity")
            if cues:
                flagged.append({
                    "source": rhee.safe_text(item.get("source")),
                    "role": rhee.safe_text(item.get("role")).lower(),
                    "cues": cues,
                })

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_polarity_guard": "applied",
            "deep_recall_polarity_flagged_count": len(flagged),
            "deep_recall_polarity_flagged": flagged[:50],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL NEGATION / POLARITY FIDELITY GUARD",
            f"Retrieved evidence records with strong negation/correction-polarity cues={len(flagged)}.",
            "Lexical relevance does not determine assertion polarity. A record containing 'work at X' may explicitly say 'I did NOT work at X'. Preserve the proposition exactly as asserted.",
            "Do not strip or overlook negation when extracting a fact, date, identity, relationship, diagnosis, employer, place, completion state or event.",
            "Read the local sentence and surrounding context before converting a retrieved passage into an autobiographical claim.",
            "A phrase such as 'not X but Y' normally contains both a rejected proposition and a replacement proposition; do not remember both as positive facts.",
            "A statement such as 'I never lived there' is evidence against the positive claim 'Doug lived there' when the identity, place and scope match.",
            "Negation in an unrelated clause does not negate the whole record. Apply polarity at the claim level, not the document level.",
            "Later explicit Doug corrections still govern same-fact conflicts under the existing correction and temporal rules.",
        ]
        if flagged:
            lines.append(
                "Sources requiring polarity-aware reading: " +
                ", ".join(item["source"] for item in flagged[:50])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
