"""Layer 28 — Deep Recall subject-fidelity guard.

Deep Recall deliberately follows gaps, entities and anchors discovered during a
full-corpus search. Those follow-through passes improve coverage, but they also
create a risk of semantic drift: an interesting adjacent memory can pull the
final answer away from what Doug actually asked.

This layer keeps the original recall subject authoritative during composition.
It does not delete retrieved evidence and does not affect ordinary Recall.
"""
import re


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def subject(query):
        text = re.sub(r"(?i)\bdeep\s+recall\b", "", rhee.safe_text(query))
        text = re.sub(r"(?i)\b(?:please|take your time|search everything you have)\b", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        original_subject = subject(query) or rhee.safe_text(query).strip()
        evidence = list(result.get("evidence") or [])
        expansion_items = sum(
            1 for item in evidence
            if any(item.get(key) for key in (
                "deep_recall_angle", "deep_recall_gap", "deep_recall_anchor",
                "deep_recall_correction_candidate"
            ))
        )
        contract = f"""
DEEP RECALL SUBJECT-FIDELITY CONTRACT
Original recall subject: {original_subject}
- The original user request remains the controlling scope even after multi-angle, gap-rescue, correction and anchor-follow-through searches.
- Newly discovered people, places, employers, schools, organisations or events are retrieval leads, not permission to change the subject.
- Include adjacent evidence only when it materially explains, verifies, dates, corrects or completes the requested subject.
- Do not turn a focused Deep Recall into a general biography merely because the archive contains interesting connected memories.
- For broad timeline/history requests, use adjacent evidence when it fills a relevant stage or transition; otherwise leave it out of the final answer.
- A highly ranked or repeatedly retrieved adjacent memory is not relevant by repetition alone.
- Preserve useful cross-domain connections when evidence supports them, but label interpretation as interpretation and keep the answer centred on Doug's question.
""".strip()
        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + contract
        output["context"] = context
        output["context_size"] = len(context)
        plan = dict(output.get("recall_plan") or {})
        plan.update({"deep_recall_subject_fidelity": "applied", "deep_recall_original_subject": original_subject, "deep_recall_expansion_evidence_items": expansion_items})
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet

    from layers.layer29_deep_recall_receipt import install as install_retrieval_receipt
    install_retrieval_receipt(rhee)
