"""Layer 60 — Deep Recall event-identity / date-conflict guard.

Testing surfaced two Army dates: January 1996 and 18 November 1996. Different
dates are not automatically contradictory if the records refer to different
events (for example enlistment, commencement, transfer, training, posting or
discharge). Deep Recall must compare the event proposition, not merely the
entity and date.

This guard flags date-bearing evidence with event-transition vocabulary and
requires same-event matching before calling dates contradictory. It creates no
timeline facts and does not affect ordinary Recall.
"""
import re

DATE_RE = re.compile(
    r"\b(?:(?:\d{1,2}\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
    r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\s+(?:19|20)\d{2}|(?:19|20)\d{2})\b",
    re.I,
)

EVENT_RE = re.compile(
    r"\b(?:joined|enlisted|commenced|started|began|entered|signed|transferred|"
    r"posted|promoted|appointed|trained|graduated|deployed|returned|left|"
    r"resigned|discharged|retired|finished|ended|purchased|bought|sold|"
    r"established|founded|opened|closed|married|engaged|separated|divorced|"
    r"diagnosed|admitted|released|certified|qualified)\b",
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
        dated_events = []
        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            dates = DATE_RE.findall(text)
            events = EVENT_RE.findall(text)
            if dates and events:
                dated_events.append({
                    "source": rhee.safe_text(item.get("source")),
                    "dates": list(dict.fromkeys(dates))[:12],
                    "event_terms": list(dict.fromkeys(e.lower() for e in events))[:12],
                })

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_event_identity_guard": "applied",
            "deep_recall_dated_event_source_count": len(dated_events),
            "deep_recall_dated_event_preview": dated_events[:40],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL EVENT-IDENTITY / DATE-CONFLICT GUARD",
            f"Retrieved sources containing both date and event-transition signals={len(dated_events)}.",
            "Two different dates involving the same person, employer, organisation or life domain are not automatically contradictory.",
            "Before declaring a date conflict, establish that both records refer to the SAME event proposition — for example both are truly dates of enlistment, not one enlistment date and one transfer/posting/training date.",
            "Preserve the source's event verb and scope. Joined, enlisted, commenced, transferred, posted, promoted, deployed, returned and discharged are not interchangeable merely because they occur in one career.",
            "If two records clearly assign different dates to the same event, surface the same-event conflict and apply authority/correction/precision rules.",
            "If the event identity is ambiguous, say the dates may refer to different stages and identify what additional evidence would resolve it; do not force a contradiction or silently merge them.",
            "Approximate dates and exact dates can coexist when they are compatible. Do not manufacture conflict from different precision levels.",
            "Do not use created_at/storage time to resolve an event-date conflict.",
        ]
        if dated_events:
            lines.append(
                "Dated-event sources for proposition-level review: " +
                ", ".join(item["source"] for item in dated_events[:40])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer61_deep_recall_answer_coverage import install as install_answer_coverage
    install_answer_coverage(rhee)
