"""Layer 7 — automatic retrieval escalation.

If an explicit personal-recall request returns suspiciously little evidence,
Rhee performs one bounded second pass with broader semantic/history cues instead
of immediately concluding the memory is absent. Retrieved evidence remains the
only authority; this layer never creates facts.
"""
import re


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_recall(query):
        text = rhee.safe_text(query).lower()
        return bool(re.search(
            r"\b(?:recall|remember|what\s+do\s+you\s+know|tell\s+me\s+about|"
            r"summari[sz]e|history|timeline|my\s+life|my\s+career|my\s+family|"
            r"my\s+school|my\s+health|my\s+relationships?)\b", text
        ))

    def evidence_key(item):
        return (rhee.safe_text(item.get("source")), rhee.safe_text(item.get("quote_source")))

    def packet(query):
        first = previous_packet(query)
        if not explicit_recall(query):
            return first
        if (first.get("recall_plan") or {}).get("status") == "needs_clarification":
            return first

        evidence = list(first.get("evidence") or [])
        # Fewer than eight sources on a broad personal-recall request is treated
        # as suspiciously sparse, not proof that Doug never supplied the history.
        if len(evidence) >= 8:
            first.setdefault("recall_plan", {})["retrieval_escalation"] = "not_needed"
            return first

        broadened = (
            rhee.safe_text(query)
            + " comprehensive deep recall history timeline childhood family school education "
              "friends relationships army military career work employment health sport major events"
        )
        second = previous_packet(broadened)
        merged = []
        seen = set()
        for item in evidence + list(second.get("evidence") or []):
            key = evidence_key(item)
            if key not in seen:
                merged.append(item)
                seen.add(key)

        # Preserve the original user query in the packet while appending the
        # broader evidence context. The answer model still sees provenance and
        # must ground claims in the returned records.
        second_context = rhee.safe_text(second.get("context"))
        first_context = rhee.safe_text(first.get("context"))
        combined_context = first_context
        if second_context and second_context not in first_context:
            combined_context += "\n\nRHEE RETRIEVAL ESCALATION — BROADER SECOND PASS\n" + second_context

        result = dict(first)
        result["evidence"] = merged
        result["context"] = combined_context
        result["context_size"] = len(combined_context)
        result["recall_active"] = bool(merged) or bool(first.get("recall_active"))
        receipt = dict(first.get("recall_plan") or {})
        receipt.update({
            "retrieval_escalation": "performed",
            "first_pass_sources": len(evidence),
            "second_pass_sources": len(second.get("evidence") or []),
            "merged_sources": len(merged),
            "sparse_recall_threshold": 8,
        })
        result["recall_plan"] = receipt
        return result

    rhee.build_context_packet = packet
