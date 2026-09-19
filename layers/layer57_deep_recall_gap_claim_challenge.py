"""Layer 57 — Deep Recall gap-claim challenge.

The schooling torture test exposed a subtle composition inconsistency: L said the
primary-school name had not been retrieved while the same evidence packet
contained multiple Woodlawn references. Those references may or may not prove
the formal school name, but they are candidate evidence that must be reconciled
before declaring the detail unretrieved.

This final guard challenges negative/gap statements against positive clues
already present in the completed packet. It does not promote a clue into a fact;
it requires L to distinguish "no evidence", "candidate clue", and "established".
Ordinary Recall is unchanged.
"""
import re
from collections import Counter

GAP_RE = re.compile(
    r"\b(?:not retrieved|didn'?t retrieve|did not retrieve|not established|"
    r"couldn'?t establish|could not establish|remaining gap|gaps?|"
    r"not reliably retrieved|not enough evidence|thin)\b",
    re.I,
)

ENTITY_RE = re.compile(
    r"\b(?:[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3}|[A-Z]{2,8})\b"
)

STOP = {
    "Doug", "Deep Recall", "Source", "User", "Assistant", "Project", "Evidence",
    "The", "This", "That", "There", "When", "Where", "What", "My", "I",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})
        thin_parts = list(plan.get("deep_recall_final_thin_parts") or [])

        entity_counts = Counter()
        entity_sources = {}
        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            source = rhee.safe_text(item.get("source"))
            for entity in ENTITY_RE.findall(text):
                entity = entity.strip()
                if entity in STOP or len(entity) < 3:
                    continue
                entity_counts[entity] += 1
                entity_sources.setdefault(entity, []).append(source)

        repeated_clues = [
            {
                "entity": entity,
                "count": count,
                "sources": list(dict.fromkeys(entity_sources.get(entity, [])))[:8],
            }
            for entity, count in entity_counts.most_common(60)
            if count >= 2
        ]

        historical_gap_sources = []
        for item in evidence:
            role = rhee.safe_text(item.get("role")).lower()
            text = rhee.safe_text(item.get("quote_source"))
            if role != "user" and GAP_RE.search(text):
                historical_gap_sources.append(rhee.safe_text(item.get("source")))

        output = dict(result)
        plan.update({
            "deep_recall_gap_claim_challenge": "applied",
            "deep_recall_gap_claim_thin_parts": thin_parts,
            "deep_recall_gap_claim_repeated_clues": repeated_clues[:40],
            "deep_recall_gap_claim_historical_gap_sources": historical_gap_sources[:30],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL GAP-CLAIM CHALLENGE",
            f"Final thin requested parts={len(thin_parts)}; repeated named clues in completed evidence={len(repeated_clues)}.",
            "Before saying a requested detail was not retrieved or not established, challenge that gap statement against the COMPLETE evidence packet.",
            "If the packet contains a plausible clue to the missing detail, do not ignore it. Decide whether the clue actually establishes the detail, merely suggests a candidate, or is unrelated.",
            "A candidate clue is not permission to invent certainty. Use wording such as 'the records repeatedly mention Woodlawn, but the retrieved evidence does not yet establish whether that is the formal primary-school name' when that is the honest evidentiary state.",
            "Do not say 'I did not retrieve the name' while simultaneously presenting a plausible name-like clue without reconciling the two statements.",
            "Historical assistant statements about old retrieval gaps are not current gap evidence.",
            "Prefer three calibrated states: ESTABLISHED by evidence; CANDIDATE/CLUE requiring qualification; genuinely NOT ESTABLISHED by this retrieval.",
            "Only report a final gap after checking whether later rescue passes or repeated primary clues have already narrowed it.",
        ]
        if repeated_clues:
            preview = "; ".join(
                f"{item['entity']} x{item['count']}"
                for item in repeated_clues[:20]
            )
            lines.append("Repeated named clues for final gap review: " + preview)

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
