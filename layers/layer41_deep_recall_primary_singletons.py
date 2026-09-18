"""Layer 41 — Deep Recall primary singleton preservation.

A unique autobiographical fact may exist in only one Doug-authored primary
record. Deep Recall must not mistake "mentioned once" for "weak" merely because
duplicate summaries or repeated themes have higher apparent frequency.

This final composition guard identifies relevant Doug-authored evidence that is
not duplicated by the same raw lineage and reminds composition to preserve
material singleton facts when they answer the question. One source is not
automatic proof; normal conflict, chronology and claim-evidence rules still
apply. Ordinary Recall is unchanged.
"""
import re
from collections import Counter

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]{2,}")
STOP = {
    "the","and","that","this","with","from","have","was","were","been","about",
    "deep","recall","doug","your","you","for","but","not","they","their","then",
    "when","where","what","which","into","after","before","because","would",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def lineage(item):
        source = rhee.safe_text(item.get("source"))
        if source.startswith("raw_catchall:"):
            return source
        raw_id = rhee.safe_text(item.get("raw_id")).strip()
        return f"raw_catchall:{raw_id}" if raw_id else source

    def query_terms(query):
        terms = []
        seen = set()
        for token in TOKEN_RE.findall(rhee.safe_text(query).lower()):
            if token in STOP or token in seen:
                continue
            terms.append(token); seen.add(token)
        return terms[:24]

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        lineages = Counter(lineage(item) for item in evidence if lineage(item))
        needles = query_terms(query)

        singleton_primary = []
        for item in evidence:
            if rhee.safe_text(item.get("role")).lower() != "user":
                continue
            lin = lineage(item)
            if not lin or lineages.get(lin, 0) != 1:
                continue
            text = rhee.safe_text(item.get("quote_source"))
            low = text.lower()
            relevance = sum(1 for term in needles if term in low)
            # Keep direct scorer as the governing relevance test; lexical overlap
            # is only useful diagnostic context.
            try:
                score = rhee.calculate_raw_score(
                    {"content": text, "role": "user"}, query
                )
            except Exception:
                score = 0
            if score > 0:
                singleton_primary.append({
                    "source": rhee.safe_text(item.get("source")),
                    "score": score,
                    "query_term_hits": relevance,
                })

        singleton_primary.sort(
            key=lambda item: (item["score"], item["query_term_hits"]),
            reverse=True,
        )
        singleton_primary = singleton_primary[:30]

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_primary_singleton_preservation": "applied",
            "deep_recall_primary_singleton_count": len(singleton_primary),
            "deep_recall_primary_singleton_sources": [
                item["source"] for item in singleton_primary
            ],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL PRIMARY-SINGLETON PRESERVATION",
            f"Relevant Doug-authored singleton lineages detected: {len(singleton_primary)}.",
            "A primary fact does not become weak merely because Doug only recorded it once.",
            "Do not let repeated assistant summaries or frequently repeated themes crowd a material one-off Doug-authored fact out of the answer.",
            "Preserve a singleton when it materially answers the requested subject and its source supports the claim.",
            "Do NOT treat singleton status as automatic truth or increased confidence: apply the same chronology, conflict, correction and claim-evidence rules.",
            "Frequency is not authority. Repetition is not independent corroboration.",
        ]
        if singleton_primary:
            lines.append(
                "Primary singleton sources for composition review: " +
                ", ".join(item["source"] for item in singleton_primary)
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
