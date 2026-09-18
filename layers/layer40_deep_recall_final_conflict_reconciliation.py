"""Layer 40 — final Deep Recall conflict reconciliation.

Authority/conflict checks run earlier in the recall chain, but later rescue passes
can add primary records, corrections, time-window evidence, aliases and
transitions after that review. A late record can therefore introduce a conflict
that the early review never saw.

This final composition guard forces the completed evidence packet back through
the conflict/authority principles before answering. It does not auto-resolve
conflicts from keywords, delete evidence or invent a preferred version.
Ordinary Recall is unchanged.
"""
import re

CONFLICT_CUE_RE = re.compile(
    r"\b(?:actually|correction|corrected|not\s+.{0,50}\s+but|wrong|mistake|"
    r"rather than|instead|clarif(?:y|ied|ication)|to be clear|supersed(?:e|ed|es)|"
    r"formerly|previously|later changed|updated)\b",
    re.I,
)

LATE_KEYS = (
    "deep_recall_component", "deep_recall_provenance_backfill",
    "deep_recall_time_window", "deep_recall_alias",
    "deep_recall_transition", "deep_recall_angle",
    "deep_recall_gap", "deep_recall_anchor",
    "deep_recall_correction_candidate",
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
        late_items = [
            item for item in evidence
            if any(item.get(key) for key in LATE_KEYS)
        ]
        user_items = [
            item for item in evidence
            if rhee.safe_text(item.get("role")).lower() == "user"
        ]
        correction_cues = [
            rhee.safe_text(item.get("source"))
            for item in evidence
            if CONFLICT_CUE_RE.search(rhee.safe_text(item.get("quote_source")))
        ]

        plan = dict(result.get("recall_plan") or {})
        output = dict(result)
        plan.update({
            "deep_recall_final_conflict_reconciliation": "applied",
            "deep_recall_final_conflict_evidence_items": len(evidence),
            "deep_recall_final_conflict_late_items": len(late_items),
            "deep_recall_final_conflict_user_items": len(user_items),
            "deep_recall_final_conflict_cue_sources": correction_cues[:30],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL FINAL AUTHORITY / CONFLICT RECONCILIATION",
            "This review applies to the COMPLETE evidence packet after all current late rescue passes.",
            f"Final evidence items={len(evidence)}; late-rescued items={len(late_items)}; Doug-authored items={len(user_items)}; records with correction/change cues={len(correction_cues)}.",
            "Before composing any concrete claim, check whether another retrieved record states a materially different version of the SAME fact.",
            "Do not call two records contradictory merely because they differ: first test whether they describe different time periods, scopes, people, places or stages.",
            "If Doug later explicitly corrects the same fact, prefer that correction under the existing authority policy.",
            "If records differ because circumstances changed over time, explain the transition rather than choosing one version.",
            "If a genuine same-fact conflict remains unresolved, surface the disagreement and preserve uncertainty instead of selecting the smoother narrative.",
            "Derived memories and assistant summaries cannot outvote a Doug-authored primary record by repetition or count.",
            "A correction/change cue is only a review signal; it is not proof of supersession without matching the underlying fact.",
        ]
        if correction_cues:
            lines.append("Correction/change cue sources for review: " + ", ".join(correction_cues[:30]))

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer41_deep_recall_primary_singletons import install as install_primary_singletons
    install_primary_singletons(rhee)
