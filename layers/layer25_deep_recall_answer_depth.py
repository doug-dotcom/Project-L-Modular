"""Layer 25 — Deep Recall answer-depth preservation.

Doug uses Recall for a quick look and Deep Recall when he explicitly wants the
archive searched properly. After expensive retrieval, composition must not throw
that value away by collapsing a broad, well-supported result into a tiny answer.
This layer calibrates answer depth to the evidence actually recovered.

It does not require verbosity when evidence is thin, and it never licenses
unsupported detail. Ordinary Recall is unchanged.
"""
import re


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def broad_request(query):
        return bool(re.search(
            r"\b(?:complete|entire|whole|full|chronological|chronology|timeline|history|"
            r"beginning|end|all|everything|across my life|life story|summari[sz]e)\b",
            rhee.safe_text(query).lower(),
        ))

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})
        source_count = len(evidence)
        primary_count = sum(1 for item in evidence if rhee.safe_text(item.get("role")).lower() == "user")
        broad = broad_request(query)
        if broad and source_count >= 20:
            depth = "detailed_structured"
        elif source_count >= 8:
            depth = "substantive"
        else:
            depth = "evidence_limited"

        contract = f"""
DEEP RECALL ANSWER-DEPTH CONTRACT
Answer-depth target: {depth}. Retrieved evidence sources: {source_count}; Doug-authored primary sources: {primary_count}.
- Deep Recall is an explicit request to trade speed for depth. Do not discard the value of a successful deep search by returning an artificially tiny summary.
- When the request is broad and evidence is rich, organise the answer into a readable chronology or thematic structure and include the important retrieved stages, transitions, people and events that answer the question.
- Prefer synthesis over an evidence dump: combine genuinely compatible records, avoid repeating duplicate tellings, and cite/source the evidence using the application's existing source format.
- Preserve material nuance, corrections, uncertainty and meaningful gaps. Do not manufacture detail merely to make the answer longer.
- If the evidence is genuinely thin, a short answer is correct. Explain the thin coverage rather than padding it.
- If Doug asked a focused question, answer that focused question even though Deep Recall searched broadly; depth does not mean irrelevant biography.
- Ordinary Recall remains the fast/compact path. This contract applies only because Doug explicitly requested Deep Recall.
""".strip()

        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + contract
        output["context"] = context
        output["context_size"] = len(context)
        plan.update({"deep_recall_answer_depth": depth, "deep_recall_answer_depth_sources": source_count, "deep_recall_answer_depth_primary_sources": primary_count, "deep_recall_answer_depth_broad_request": broad})
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet

    from layers.layer26_deep_recall_temporal_truth import install as install_temporal_truth
    install_temporal_truth(rhee)
