"""Layer 30 — Deep Recall question decomposition / coverage checklist.

A single Deep Recall request can contain several distinct information needs. A
large evidence packet can answer the dominant part well while silently missing a
secondary part. This layer decomposes compound/broad requests into a compact
composition checklist so L audits each requested dimension before answering.

It does not create facts, perform speculative inference, or affect ordinary
Recall. Missing coverage remains a retrieval/answer limitation, not proof that a
memory was never stored.
"""
import re

MAX_PARTS = 8


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def clean_subject(query):
        text = re.sub(r"(?i)\bdeep\s+recall\b", "", rhee.safe_text(query))
        text = re.sub(r"(?i)\b(?:please|take your time|search everything you have)\b", "", text)
        return re.sub(r"\s+", " ", text).strip(" ,.;:-")

    def decompose(query):
        subject = clean_subject(query)
        if not subject:
            return []
        # Split only on explicit request structure. Do not invent subquestions.
        chunks = re.split(r"\s*(?:;|\n|\band then\b|\bas well as\b|\balso\b)\s*", subject, flags=re.I)
        parts = []
        seen = set()
        for chunk in chunks:
            chunk = re.sub(r"\s+", " ", chunk).strip(" ,.;:-")
            if not chunk:
                continue
            key = chunk.lower()
            if key not in seen:
                parts.append(chunk)
                seen.add(key)
            if len(parts) >= MAX_PARTS:
                break
        # A broad request may be one coherent dimension; keep it whole rather
        # than mechanically splitting every occurrence of 'and'.
        return parts or [subject]

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        parts = decompose(query)
        if not parts:
            return result

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_question_decomposition": "applied",
            "deep_recall_question_parts": parts,
            "deep_recall_question_part_count": len(parts),
        })
        output["recall_plan"] = plan

        checklist = [
            "DEEP RECALL QUESTION-COVERAGE CHECKLIST",
            "Before composing, verify that the answer addresses every explicit information need in Doug's request that is supported by retrieved evidence.",
        ]
        for index, part in enumerate(parts, 1):
            checklist.append(f"{index}. {part}")
        checklist.extend([
            "Do not let strong evidence for one part hide weak or missing evidence for another part.",
            "If one requested part remains thin after Deep Recall, answer the supported parts and identify that specific gap honestly.",
            "Do not invent extra subquestions or expand beyond the original subject merely to make the answer broader.",
            "A thin part means not established by this retrieval, not that the memory was never stored.",
        ])

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(checklist)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
