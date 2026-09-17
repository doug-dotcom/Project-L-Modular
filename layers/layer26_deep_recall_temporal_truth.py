"""Layer 26 — Deep Recall temporal-truth guard.

A long autobiographical archive naturally contains facts that were true at one
time and later changed. Deep Recall must not flatten historical and current
states together merely because both records are relevant. This layer adds an
explicit temporal composition contract after retrieval.

It creates no facts and does not use storage timestamps as event dates.
Ordinary Recall is unchanged.
"""
import re


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        dated_sources = 0
        current_cues = 0
        historical_cues = 0
        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            if re.search(r"\b(?:19|20)\d{2}\b", text):
                dated_sources += 1
            if re.search(r"\b(?:currently|current|now|today|still|as of|present)\b", text, re.I):
                current_cues += 1
            if re.search(r"\b(?:formerly|previously|used to|then|at the time|later|before|after|ended|stopped|left|changed)\b", text, re.I):
                historical_cues += 1

        contract = """
DEEP RECALL TEMPORAL-TRUTH CONTRACT
- Treat autobiographical facts as time-scoped when the evidence supports a period, transition or later change.
- Do not collapse "was true then" into "is true now", or a current fact backward into earlier life.
- Distinguish event time, effective period and recording time. created_at/storage timestamps do NOT become event dates unless the record explicitly says the event occurred then.
- When two records differ because Doug's circumstances changed over time, prefer a timeline/transition explanation over calling them contradictory.
- Use the later record for present-state claims only when it actually establishes a later/current state; recency of storage alone is not enough.
- Preserve approximate dates as approximate. Do not manufacture a precise month/day from a year, age, ordering clue or database timestamp.
- For "before/after", "when", "at that time", "currently" and life-stage questions, bind each claim to the correct period before composing the answer.
- If the temporal relationship cannot be established from retrieved evidence, say the order/date is uncertain rather than choosing the smoothest chronology.
""".strip()

        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + contract
        output["context"] = context
        output["context_size"] = len(context)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_temporal_truth": "applied",
            "deep_recall_temporal_dated_sources": dated_sources,
            "deep_recall_temporal_current_cues": current_cues,
            "deep_recall_temporal_historical_cues": historical_cues,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
