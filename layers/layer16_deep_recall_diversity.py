"""Layer 16 — deep-recall evidence diversity.

Deep recall now has breadth, but broad historical corpora can contain repeated
summaries and near-duplicate retellings. Prevent one repeated story from
consuming the expanded evidence window. This layer preserves the highest-ranked
source-linked item in each near-duplicate cluster while retaining distinct
sources, domains and events.

No facts are created or rewritten.
"""
import re

MAX_PER_SOURCE_FAMILY = 14


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def tokens(text):
        return set(re.findall(r"[a-z0-9']+", rhee.safe_text(text).lower()))

    def near_duplicate(a, b):
        ta, tb = tokens(a), tokens(b)
        if not ta or not tb:
            return False
        overlap = len(ta & tb)
        union = len(ta | tb)
        return union > 0 and overlap / union >= 0.72

    def source_family(source):
        value = rhee.safe_text(source)
        return value.split(":", 1)[0] if ":" in value else value

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        kept = []
        family_counts = {}
        suppressed = 0

        for item in evidence:
            quote = rhee.safe_text(item.get("quote_source"))
            family = source_family(item.get("source"))
            if family_counts.get(family, 0) >= MAX_PER_SOURCE_FAMILY:
                suppressed += 1
                continue
            if any(near_duplicate(quote, rhee.safe_text(old.get("quote_source"))) for old in kept):
                suppressed += 1
                continue
            kept.append(item)
            family_counts[family] = family_counts.get(family, 0) + 1

        output = dict(result)
        output["evidence"] = kept
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({
            "deep_recall_diversity": "applied",
            "deep_recall_sources_before_diversity": len(evidence),
            "deep_recall_sources_after_diversity": len(kept),
            "deep_recall_near_duplicates_suppressed": suppressed,
            "deep_recall_source_families": family_counts,
        })
        output["recall_plan"] = receipt

        context = rhee.safe_text(output.get("context"))
        context += (
            "\n\nDEEP RECALL DIVERSITY CONTRACT\n"
            "The evidence list has been de-duplicated for answer planning. Repeated retellings must not crowd out distinct events, periods or domains. "
            "Prefer a broad set of independently useful retrieved memories while preserving provenance and conflicts."
        )
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer17_deep_recall_primary_evidence import install as install_primary_evidence
    install_primary_evidence(rhee)
