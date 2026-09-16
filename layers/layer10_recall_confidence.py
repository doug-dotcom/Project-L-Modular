"""Layer 10 — recall confidence and absence semantics.

Prevents a retrieval miss from being described as a memory/storage absence.
Classifies the outcome of the retrieval pipeline after escalation, coverage and
authority review, and gives the answer model precise language for uncertainty.
This layer never invents evidence and never claims database absence merely from
an unsuccessful search.
"""


def install(rhee):
    previous_packet = rhee.build_context_packet

    def packet(query):
        result = previous_packet(query)
        receipt = dict(result.get("recall_plan") or {})
        if receipt.get("status") == "needs_clarification":
            return result

        evidence = list(result.get("evidence") or [])
        count = len(evidence)
        escalated = receipt.get("retrieval_escalation") == "performed"
        coverage = receipt.get("coverage_check")
        budget_exceeded = receipt.get("status") == "budget_exceeded"

        if budget_exceeded:
            state = "retrieval_incomplete"
            confidence = "low"
            wording = "Retrieval did not complete within its evidence budget; do not infer that missing material is absent from memory."
        elif count == 0:
            state = "not_retrieved_after_search"
            confidence = "low"
            wording = "No supporting record was retrieved in this search. This is not evidence that the information is not stored."
        elif count < 8:
            state = "sparse_retrieval"
            confidence = "low_to_moderate"
            wording = "Some evidence was retrieved, but coverage is sparse. Describe the retrieved material and identify the retrieval gap without claiming the memory is absent."
        elif coverage == "incomplete":
            state = "partial_coverage"
            confidence = "moderate"
            wording = "Substantial evidence was retrieved, but expected memory neighbourhoods remain uncovered. State which parts are supported and which were not retrieved."
        else:
            state = "supported_retrieval"
            confidence = "high" if count >= 12 else "moderate_to_high"
            wording = "Retrieved evidence is sufficient to answer from memory, subject to provenance and conflict guardrails."

        # Critical semantic distinction exposed by Doug's schooling tests:
        # retrieval absence != storage absence. Only a dedicated exhaustive
        # database verification may ever support a claim that something is not
        # stored; ordinary Rhee recall must use 'not retrieved' language.
        policy = f"""
RHEE RECALL CONFIDENCE REVIEW
OUTCOME: {state}
EVIDENCE SOURCES: {count}
CONFIDENCE: {confidence}
RETRIEVAL ESCALATED: {str(escalated).lower()}
GUIDANCE: {wording}
ABSENCE RULE: Never say or imply 'I do not have this memory', 'it is not in my records', or 'it was never stored' solely because retrieval returned little or nothing. Say 'I did not retrieve it in this search' unless a separate exhaustive storage-verification operation proves absence.
""".strip()

        context = rhee.safe_text(result.get("context"))
        context = policy + "\n\n" + context

        output = dict(result)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_confidence"] = {
            "state": state,
            "confidence": confidence,
            "evidence_sources": count,
            "retrieval_escalated": escalated,
            "storage_absence_verified": False,
        }
        receipt.update({
            "recall_confidence_state": state,
            "recall_confidence": confidence,
            "storage_absence_verified": False,
            "absence_semantics": "retrieval_miss_is_not_storage_absence",
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet
