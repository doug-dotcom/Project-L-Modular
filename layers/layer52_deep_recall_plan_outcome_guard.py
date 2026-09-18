"""Layer 52 — Deep Recall superseded-plan / intention guard.

Personal archives contain plans, wishes, options and intentions that may never
have happened. "I plan to...", "we might...", or "I want to..." should not later
be recalled as a completed event unless later evidence establishes completion.

This guard separates intended/proposed future states from completed historical
events and gives later completion/cancellation evidence priority for outcome
claims. It does not discard plans; plans are valid memories when the question is
about what Doug intended at the time. Ordinary Recall is unchanged.
"""
import re

PLAN_RE = re.compile(
    r"\b(?:I plan(?:ned)? to|planning to|I intend(?:ed)? to|I want(?:ed)? to|"
    r"I hope(?:d)? to|I might|I may|we might|we may|thinking about|considering|"
    r"going to|will probably|booked to|scheduled to|due to|expected to|"
    r"could do|should do|let'?s do|we'?ll do)\b", re.I
)
COMPLETION_RE = re.compile(
    r"\b(?:done|completed|finished|achieved|went|did it|confirmed|actually did|"
    r"certified|graduated|started|joined|paid|bought|sold|booked|arrived|returned|"
    r"cancelled|canceled|didn'?t|did not|decided not to|changed my mind)\b", re.I
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
        plan_sources = []
        outcome_sources = []

        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            source = rhee.safe_text(item.get("source"))
            if PLAN_RE.search(text):
                plan_sources.append(source)
            if COMPLETION_RE.search(text):
                outcome_sources.append(source)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_plan_outcome_guard": "applied",
            "deep_recall_plan_source_count": len(plan_sources),
            "deep_recall_outcome_source_count": len(outcome_sources),
            "deep_recall_plan_source_preview": plan_sources[:40],
            "deep_recall_outcome_source_preview": outcome_sources[:40],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL PLAN / OUTCOME FIDELITY GUARD",
            f"Plan/intention-like evidence records={len(plan_sources)}; completion/cancellation-like evidence records={len(outcome_sources)}.",
            "Keep intentions, plans, bookings, options, hopes and proposed future actions distinct from events that later actually occurred.",
            "A statement such as 'I plan to do X', 'we might do X', or 'I am booked to do X' establishes the plan/status at that time; it does not by itself establish that X was completed.",
            "For a historical outcome claim, look for later evidence of completion, cancellation, change or non-occurrence. If none is retrieved, describe the item as a plan/intention rather than silently converting it into history.",
            "If later Doug-authored evidence says the plan changed, was cancelled, or happened differently, use that later outcome evidence under the temporal/conflict rules.",
            "If Doug asks what he was planning or hoping at a past point, preserve the plan as a valid historical fact about his intention at that time.",
            "Bookings and scheduled events are not completion evidence unless the source itself also establishes completion.",
        ]

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer53_deep_recall_polarity_guard import install as install_polarity_guard
    install_polarity_guard(rhee)
