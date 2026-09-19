"""Layer 62 — Deep Recall operational-residue evidence filter.

Layer 56 identified stale operational assistant text, but testing showed that
instruction alone was not sufficient: generic verification-withheld boilerplate
still appeared repeatedly in the final answer. This layer makes the quarantine
structural for explicit Deep Recall.

Assistant/system/tool records whose content is primarily reconnect, interrupted
task, saved-answer, tool/deployment status, generic sign-off, or verification-
withheld boilerplate are removed from the final evidence list unless Doug's
current query explicitly asks about that historical interaction.

Stored raw_catchall rows are NEVER deleted or modified. This is query-time
evidence filtering only. User-authored records are never removed by this layer.
Ordinary Recall is unchanged.
"""
import re

OPERATIONAL_RE = re.compile(
    r"(?:"
    r"could not reconnect|couldn'?t reconnect|cannot reconnect|"
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

HISTORICAL_FAILURE_RE = re.compile(
    r"(?:"
    r"I cannot honestly reconstruct|"
    r"I cannot currently retrieve|"
    r"I do not currently have reliable|"
    r"I don'?t currently have reliable|"
    r"not present in enough detail here"
    r")",
    re.I,
)


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def asks_about_history(query):
        text = rhee.safe_text(query).lower()
        return any(term in text for term in (
            "what did l say", "what did you say", "old answer",
            "previous answer", "retrieval failure", "reconnect",
            "interrupted task", "saved answer", "assistant message",
            "conversation history", "what happened when",
        ))

    def is_operational(item):
        role = rhee.safe_text(item.get("role")).lower()
        if role not in {"assistant", "system", "tool"}:
            return False
        text = rhee.safe_text(item.get("quote_source"))
        return bool(OPERATIONAL_RE.search(text) or HISTORICAL_FAILURE_RE.search(text))

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        allow = asks_about_history(query)
        removed = []

        if allow:
            filtered = evidence
        else:
            filtered = []
            for item in evidence:
                if is_operational(item):
                    removed.append(rhee.safe_text(item.get("source")))
                    continue
                filtered.append(item)

        output = dict(result)
        output["evidence"] = filtered
        output["recall_active"] = bool(filtered) or bool(result.get("recall_active"))

        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_operational_residue_filter": "applied",
            "deep_recall_operational_residue_history_requested": allow,
            "deep_recall_operational_residue_removed_count": len(removed),
            "deep_recall_operational_residue_removed_sources": removed[:80],
            "deep_recall_operational_residue_evidence_remaining": len(filtered),
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL STRUCTURAL OPERATIONAL-RESIDUE FILTER",
            f"Operational/stale assistant evidence removed from final evidence list={len(removed)}; evidence remaining={len(filtered)}.",
            "This filtering is query-time only. No stored memory was deleted or modified.",
            "User-authored records are never removed by this filter.",
            "Do not cite, quote or replay removed operational sources in the current autobiographical answer.",
            "If useful autobiographical evidence existed only inside a removed assistant record, prefer the underlying primary/derived source already retrieved. If no supporting source remains, treat that detail as unsupported rather than replaying stale boilerplate.",
        ]
        if allow:
            lines.append(
                "Doug explicitly asked about historical assistant/system interaction, so operational records were retained for this query."
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
