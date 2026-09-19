"""Layer 56 — Deep Recall response-hygiene / stale-task replay isolation.

Testing exposed a final-answer contamination failure: a good schooling Deep
Recall was followed by unrelated historical assistant text such as reconnect
messages, interrupted-task notices, an old career recall and a generic good-night
reply. Those records may legitimately exist in raw_catchall, but they are
conversation/transport history, not autobiographical evidence to replay.

This layer identifies operational assistant/system residue and stale-answer
patterns in the completed evidence packet. It preserves the stored records and
their provenance but explicitly quarantines them from user-facing composition
unless Doug's current question is specifically about that historical interaction.
Ordinary Recall is unchanged.
"""
import re

OPERATIONAL_RE = re.compile(
    r"(?:"
    r"could not reconnect|couldn't reconnect|cannot reconnect|"
    r"task was interrupted|request is saved|saved answers|"
    r"please review before sending|action may already have happened|"
    r"try again shortly|connection (?:failed|lost|interrupted)|"
    r"tool (?:failed|error)|deployment (?:queued|building|failed)|"
    r"I couldn'?t verify the supporting record for this part|"
    r"I could not verify the supporting record for this part|"
    r"so I'?ve withheld it|so I have withheld it|"
    r"good night!?\s*(?:😊|❤️|$)|"
    r"hope you have a restful sleep"
    r")",
    re.I,
)

OLD_RECALL_FAILURE_RE = re.compile(
    r"(?:"
    r"I cannot honestly reconstruct|"
    r"I cannot currently retrieve|"
    r"I do not currently have reliable|"
    r"I don'?t currently have reliable|"
    r"the material currently retrievable|"
    r"retrieval gap|"
    r"not present in enough detail here"
    r")",
    re.I,
)


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def current_query_is_about_system_history(query):
        text = rhee.safe_text(query).lower()
        return any(term in text for term in (
            "what did l say", "what did you say", "old answer",
            "previous answer", "retrieval failure", "reconnect",
            "interrupted task", "saved answer", "assistant message",
            "conversation history",
        ))

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        quarantined = []
        old_failures = []

        for item in evidence:
            role = rhee.safe_text(item.get("role")).lower()
            if role not in {"assistant", "system", "tool"}:
                continue
            text = rhee.safe_text(item.get("quote_source"))
            source = rhee.safe_text(item.get("source"))
            cues = []
            if OPERATIONAL_RE.search(text):
                cues.append("operational_or_transport_residue")
            if OLD_RECALL_FAILURE_RE.search(text):
                cues.append("historical_retrieval_failure")
                old_failures.append(source)
            if cues:
                quarantined.append({"source": source, "cues": cues})

        allow_history = current_query_is_about_system_history(query)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_response_hygiene": "applied",
            "deep_recall_response_hygiene_quarantined_count": len(quarantined),
            "deep_recall_response_hygiene_quarantined": quarantined[:60],
            "deep_recall_historical_retrieval_failures_count": len(old_failures),
            "deep_recall_response_hygiene_history_requested": allow_history,
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL RESPONSE-HYGIENE / STALE-TASK REPLAY ISOLATION",
            f"Assistant/system operational or stale-recall records flagged={len(quarantined)}.",
            "Historical assistant/system/tool messages may remain stored in raw_catchall for continuity and auditability. Their presence in the evidence packet does NOT authorise replaying them into the current answer.",
            "Do not emit old reconnect notices, interrupted-task notices, saved-answer notices, deployment/tool status, generic greetings/good-nights, or verification-withheld boilerplate as part of an autobiographical Deep Recall answer.",
            "Do not append an old assistant answer merely because it was retrieved near relevant evidence. Compose a NEW answer to Doug's CURRENT question from claim-level evidence.",
            "An old assistant statement that retrieval failed is evidence of that historical retrieval outcome only; it is not evidence that the underlying autobiographical fact is absent.",
            "If an assistant record contains both useful autobiographical evidence and operational residue, use only the supported factual content and omit the operational boilerplate.",
            "Never reproduce the sentence 'I couldn't verify the supporting record for this part, so I've withheld it' without identifying a current, specific claim that was actually withheld. Prefer simply omitting an unsupported claim or naming the precise remaining gap.",
            "End the response when the current answer is complete. Do not continue with unrelated historical assistant text.",
        ]
        if allow_history:
            lines.append(
                "Doug's current query appears to ask about historical assistant/system interaction, so quarantined records may be discussed when directly relevant, with their historical role made explicit."
            )
        elif quarantined:
            lines.append(
                "Quarantined source IDs — do not replay operational text into this answer: " +
                ", ".join(item["source"] for item in quarantined[:60])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
