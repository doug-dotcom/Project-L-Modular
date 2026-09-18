"""Layer 45 — Deep Recall stale-summary quarantine.

Historical assistant summaries are useful navigation aids, but they can contain
old retrieval gaps, outdated states, tentative interpretations or facts later
corrected by Doug. Deep Recall should not let a polished old summary outrank the
primary evidence merely because it reads coherently.

This final composition guard identifies assistant-authored summary-like records
for caution when primary/user evidence is also available. It does not delete
summaries or assume they are wrong. Ordinary Recall is unchanged.
"""
import re

SUMMARY_RE = re.compile(
    r"\b(?:summary|summarise|summarize|timeline|overview|lock[- ]?in|continuity|"
    r"handover|daily report|recap|what I know|here'?s what|the clearest record|"
    r"honest recall|retrieval gap|I cannot currently retrieve|I don't currently have)\b",
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
        assistant_summaries = []
        user_sources = []

        for item in evidence:
            source = rhee.safe_text(item.get("source"))
            role = rhee.safe_text(item.get("role")).lower()
            text = rhee.safe_text(item.get("quote_source"))
            if role == "user":
                user_sources.append(source)
            elif role in {"assistant", "system"} and SUMMARY_RE.search(text):
                assistant_summaries.append(source)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_stale_summary_quarantine": "applied",
            "deep_recall_assistant_summary_candidates": assistant_summaries[:50],
            "deep_recall_assistant_summary_candidate_count": len(assistant_summaries),
            "deep_recall_user_primary_available_count": len(user_sources),
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL STALE-SUMMARY QUARANTINE",
            f"Assistant/system summary-like evidence detected={len(assistant_summaries)}; Doug-authored evidence items available={len(user_sources)}.",
            "Historical assistant summaries are secondary navigation/synthesis evidence. Do not let their polished wording or apparent completeness outrank Doug-authored primary evidence.",
            "An old assistant statement about a retrieval gap, missing memory, current state or interpretation describes what that assistant retrieved or inferred at that time; it is not automatically an authoritative fact about the archive or Doug.",
            "Where a summary is consistent with primary evidence, it may help organise the answer. Where it conflicts with a Doug-authored record or later Doug correction, follow the existing authority/conflict rules.",
            "Do not discard a summary merely because it is assistant-authored; quarantine means lower evidentiary authority, not deletion.",
            "Do not use several summaries repeating the same primary fact as independent corroboration.",
            "For current-state claims, require evidence that actually establishes the later/current state; a recent storage date on an old summary is not enough.",
        ]
        if assistant_summaries:
            lines.append(
                "Summary-like secondary sources for caution: " +
                ", ".join(assistant_summaries[:50])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
