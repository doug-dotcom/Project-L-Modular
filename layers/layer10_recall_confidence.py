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
        independence = (
            result.get("evidence_independence")
            if isinstance(result.get("evidence_independence"), dict)
            else {}
        )
        independent_lineages = int(independence.get("independent_lineages") or 0)
        governance_complete = independence.get("governance_metadata_complete") is True
        governed_count = int(independence.get("governed_evidence_items") or 0)
        escalated = receipt.get("retrieval_escalation") == "performed"
        coverage = receipt.get("coverage_check")
        conflict_policy = receipt.get("conflict_policy")
        authority_reviewed = receipt.get("authority_review") == "applied"
        unresolved_conflict = receipt.get("unresolved_conflict") is True
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
        elif unresolved_conflict:
            state = "conflicted_retrieval"
            confidence = "moderate"
            wording = "Substantial evidence was retrieved, but a genuine same-fact conflict remains unresolved. Surface the disagreement and do not collapse it into a single confident narrative."
        else:
            state = "supported_retrieval"
            if governance_complete and governed_count == count and independent_lineages >= 3:
                confidence = "high" if independent_lineages >= 6 else "moderate_to_high"
                wording = "Retrieved evidence has governed provenance and independent lineage support sufficient to answer from memory, subject to conflict guardrails."
            else:
                confidence = "moderate"
                wording = "Retrieved evidence is substantial, but governance completeness or independent-lineage support is limited. Answer from the retrieved material without overstating certainty."

        # Critical semantic distinction exposed by Doug's schooling tests:
        # retrieval absence != storage absence. Only a dedicated exhaustive
        # database verification may ever support a claim that something is not
        # stored; ordinary Rhee recall must use 'not retrieved' language.
        policy = f"""
RHEE RECALL CONFIDENCE REVIEW
OUTCOME: {state}
EVIDENCE SOURCES: {count}
INDEPENDENT LINEAGES: {independent_lineages}
GOVERNED EVIDENCE: {governed_count}
GOVERNANCE COMPLETE: {str(governance_complete).lower()}
AUTHORITY REVIEWED: {str(authority_reviewed).lower()}
UNRESOLVED CONFLICT: {str(unresolved_conflict).lower()}
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
            "independent_lineages": independent_lineages,
            "governed_evidence_sources": governed_count,
            "governance_metadata_complete": governance_complete,
            "authority_reviewed": authority_reviewed,
            "conflict_policy": conflict_policy,
            "unresolved_conflict": unresolved_conflict,
            "retrieval_escalated": escalated,
            "storage_absence_verified": False,
        }
        receipt.update({
            "recall_confidence_state": state,
            "recall_confidence": confidence,
            "recall_conflict_state": "unresolved" if unresolved_conflict else "none_reported",
            "storage_absence_verified": False,
            "absence_semantics": "retrieval_miss_is_not_storage_absence",
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet
