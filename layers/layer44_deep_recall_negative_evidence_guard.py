"""Layer 44 — final Deep Recall negative-evidence guard.

A completed Deep Recall can still fail to retrieve a particular fact. That is
useful information about this retrieval run, but it is not evidence that Doug
never said it, that the event never happened, or that the archive contains no
record of it.

Earlier layers establish this principle during retrieval. This final composition
guard applies it after all current rescue passes so user-facing absence language
stays calibrated to what was actually searched and found.
Ordinary Recall is unchanged.
"""
import re

ABSENCE_RE = re.compile(
    r"\b(?:no evidence|no record|nothing|never told|never said|not stored|"
    r"does not exist|isn't there|is not there|cannot find|couldn't find|"
    r"do not have|don't have|no memory|no memories)\b",
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
        plan = dict(result.get("recall_plan") or {})
        thin = list(plan.get("deep_recall_final_thin_parts") or [])
        saturation = rhee.safe_text(plan.get("deep_recall_saturation", "unknown"))
        full_corpus = plan.get(
            "deep_recall_full_corpus",
            plan.get("deep_recall_mode", "requested"),
        )

        # Detect absence-like wording in retrieved evidence only as a diagnostic:
        # an old assistant saying "I don't have that" must not become evidence of
        # actual archival absence.
        historical_absence_statements = []
        for item in evidence:
            if rhee.safe_text(item.get("role")).lower() == "user":
                continue
            if ABSENCE_RE.search(rhee.safe_text(item.get("quote_source"))):
                historical_absence_statements.append(
                    rhee.safe_text(item.get("source"))
                )

        output = dict(result)
        plan.update({
            "deep_recall_negative_evidence_guard": "applied",
            "deep_recall_negative_evidence_thin_parts": thin,
            "deep_recall_negative_evidence_saturation": saturation,
            "deep_recall_negative_evidence_full_corpus": full_corpus,
            "deep_recall_historical_absence_statement_sources":
                historical_absence_statements[:30],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL FINAL NEGATIVE-EVIDENCE GUARD",
            "Calibrate all absence language to retrieval evidence. Failure to retrieve a fact is not proof that Doug never said it, that it was never stored, or that the event did not happen.",
            "For a thin requested part, prefer wording such as: 'I did not retrieve enough reliable evidence for that part in this Deep Recall' or 'the retrieved evidence does not establish that detail.'",
            "Only make a stronger archive-wide absence claim if the system has an explicit, reliable capability that proves exhaustive absence for that exact proposition; ordinary ranking, saturation, or a full-corpus scan with imperfect matching is not such proof.",
            "Do not recycle an older assistant statement like 'I don't have that memory' as evidence of absence. It records a past retrieval outcome, not necessarily the state of the archive.",
            "Saturation means later search passes produced few new distinct records; it does not prove a missing fact is absent.",
            "A final coverage state of THIN describes this retrieval packet only.",
            "If evidence is present, answer from it. If evidence is genuinely insufficient, name the limitation precisely without turning uncertainty into a negative autobiographical fact.",
        ]
        if historical_absence_statements:
            lines.append(
                "Historical assistant absence statements detected and NOT to be treated as archive truth: " +
                ", ".join(historical_absence_statements[:30])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
