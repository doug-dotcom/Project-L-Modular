"""Layer 24 — Deep Recall claim/evidence contract.

Deep Recall can now retrieve a very large and varied evidence packet. The final
risk is composition drift: the answer model may blend several records into a
smooth biography and accidentally state an inference as if it were retrieved
fact. This layer adds a strict composition contract for explicit Deep Recall.

It does not create, delete, rank or rewrite memories. It tells composition to
bind concrete autobiographical claims to retrieved evidence and to label
inference, uncertainty and unresolved conflict honestly.
"""


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        user_sources = sum(1 for item in evidence if rhee.safe_text(item.get("role")).lower() == "user")
        source_count = len(evidence)

        contract = """
DEEP RECALL CLAIM-EVIDENCE CONTRACT
- Build the answer from retrieved source-linked evidence, not from a plausible life story.
- Every concrete autobiographical claim (person, place, school, employer, role, event, date, age, sequence, achievement, diagnosis or relationship fact) must be supported by at least one retrieved record in this packet.
- Do not merge two records into a new factual claim unless the relationship between them is itself supported or clearly labelled as synthesis/inference.
- Recording/created_at timestamps are evidence about when a record was stored, not automatically when the life event occurred.
- If evidence supports the event but not an exact date/order, state the event and keep the date/order approximate or unknown.
- If primary records conflict and the correction policy cannot resolve them, surface the conflict rather than choosing the smoother story.
- Assistant/model summaries may help organise evidence but cannot upgrade an unsupported detail into fact.
- For broad requests, distinguish evidence-supported chronology from genuinely thin intervals. Never fill a thin interval just to make the narrative complete.
- "Not retrieved" and "not established by this Deep Recall" do not mean "never stored" or "never happened".
""".strip()

        output = dict(result)
        context = rhee.safe_text(output.get("context"))
        if contract not in context:
            context += "\n\n" + contract
        output["context"] = context
        output["context_size"] = len(context)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_claim_evidence_contract": "applied",
            "deep_recall_claim_evidence_sources": source_count,
            "deep_recall_claim_evidence_user_sources": user_sources,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet

    from layers.layer25_deep_recall_answer_depth import install as install_answer_depth
    install_answer_depth(rhee)
