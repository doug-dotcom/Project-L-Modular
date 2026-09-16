"""Layer 14 — deep recall self-audit before answer.

A full scan and broad evidence packet are useful only if L notices obvious gaps
before composing the final answer. For explicit/inherited deep recall, append a
non-generative audit contract: inspect scope, chronology, source authority,
contradictions and suspicious gaps before answering. The audit cannot invent
facts or convert recording timestamps into event dates.
"""


def install(rhee):
    previous_packet = rhee.build_context_packet

    def is_deep(query, result):
        text = rhee.safe_text(query).lower()
        receipt = dict(result.get("recall_plan") or {})
        return (
            rhee.term_in_text("deep recall", text)
            or bool(result.get("deep_recall"))
            or receipt.get("deep_recall_contract") == "full_corpus_scan"
            or receipt.get("deep_recall_followup") == "inherited_previous_recall"
        )

    def packet(query):
        result = previous_packet(query)
        if not is_deep(query, result):
            return result

        output = dict(result)
        context = rhee.safe_text(output.get("context"))
        audit = """
DEEP RECALL PRE-ANSWER SELF-AUDIT
Before composing the answer, silently audit the retrieved evidence:
1. Restate internally what scope Doug actually asked for; do not answer a narrower question merely because those records ranked highest.
2. Check whether the evidence covers the beginning, middle and end of any requested life period or chronology. A large unexplained gap is a retrieval/coverage warning, not proof nothing happened.
3. Prefer Doug-authored primary evidence and governed/canonical facts over old assistant summaries when they conflict.
4. Separate event dates from recording/created_at dates. A later retelling does not move an old event into the recording year.
5. Look for contradictory names, dates, roles, places or sequences and disclose unresolved conflicts rather than silently choosing one.
6. Use all relevant supplied deep-recall evidence, not merely the first or highest-ranked cluster.
7. If coverage is still genuinely thin after the full-corpus scan, say exactly which part is thin. Never say a memory is not stored unless storage absence was actually verified.
8. Do not invent connective tissue between isolated records. Inference must be labelled as inference.
This audit changes answer discipline only; retrieved source evidence remains the authority.
""".strip()
        output["context"] = context + "\n\n" + audit
        output["context_size"] = len(output["context"])
        receipt = dict(output.get("recall_plan") or {})
        receipt["deep_recall_self_audit"] = "required"
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet
