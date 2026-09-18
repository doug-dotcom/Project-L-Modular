"""Layer 39 — Deep Recall chronology confidence map.

A broad historical answer can contain well-supported events while the ordering
between those events remains less certain. Deep Recall should not turn a set of
dated and undated memories into an artificially precise timeline.

This final composition guard inventories explicit event-year signals and warns
composition to separate established dates/order from approximate or undated
sequence. It does not infer dates from created_at and does not create facts.
Ordinary Recall is unchanged.
"""
import re
from collections import Counter

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
APPROX_RE = re.compile(
    r"\b(?:about|around|approximately|approx\.?|roughly|circa|c\.|early|mid|late|"
    r"sometime|probably|I think|I believe)\b", re.I
)


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        year_counts = Counter()
        explicit_dated = 0
        approximate_dated = 0
        undated = 0

        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            years = YEAR_RE.findall(text)
            if not years:
                undated += 1
                continue
            explicit_dated += 1
            if APPROX_RE.search(text):
                approximate_dated += 1
            for year in set(years):
                year_counts[year] += 1

        ordered_years = sorted(year_counts, key=int)
        plan = dict(result.get("recall_plan") or {})
        broad = bool(
            re.search(
                r"\b(?:complete|entire|whole|full|chronolog|timeline|history|career|"
                r"schooling|life before|life after|working life|across my life)\b",
                rhee.safe_text(query),
                re.I,
            )
        )

        output = dict(result)
        plan.update({
            "deep_recall_chronology_confidence": "applied",
            "deep_recall_chronology_broad_request": broad,
            "deep_recall_chronology_dated_sources": explicit_dated,
            "deep_recall_chronology_approx_dated_sources": approximate_dated,
            "deep_recall_chronology_undated_sources": undated,
            "deep_recall_chronology_years": ordered_years[:80],
        })
        output["recall_plan"] = plan

        if broad:
            lines = [
                "DEEP RECALL CHRONOLOGY-CONFIDENCE MAP",
                f"Evidence with explicit year signal={explicit_dated}; with approximate-date language={approximate_dated}; without explicit year signal={undated}.",
                "Years appearing somewhere in retrieved evidence: " + (", ".join(ordered_years[:80]) if ordered_years else "none explicitly detected") + ".",
                "Use this only as a chronology quality guard, not as a generated timeline.",
                "A year appearing in a record does not automatically date every event in that record.",
                "Do not infer event dates from created_at/storage timestamps.",
                "When evidence establishes an event but not its exact year/order, preserve that uncertainty with language such as 'around', 'by then', 'later', or 'the retrieved records do not establish the exact date'.",
                "When two events are both supported but their relative order is not established, do not invent a sequence merely to make the narrative flow.",
                "Prefer an honest approximate chronology over a falsely precise one.",
            ]
            context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
            output["context"] = context
            output["context_size"] = len(context)

        return output

    rhee.build_context_packet = packet
