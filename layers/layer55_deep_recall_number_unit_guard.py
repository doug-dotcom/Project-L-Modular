"""Layer 55 — Deep Recall number / unit fidelity guard.

Autobiographical archives contain money, dates, weights, distances, doses,
counts, percentages and other quantities. Retrieval can find the right record
while composition silently changes units, currency, precision or scope.

This guard flags quantitative evidence and requires numbers to stay attached to
their stated unit/currency/time basis. It does not perform conversions or
recalculate values unless the answer explicitly needs that and the conversion is
clearly labelled. Ordinary Recall is unchanged.
"""
import re

NUMBER_RE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?\b|[$€£]\s?\d|\b(?:AUD|USD|NZD|IDR)\b|"
    r"\b\d+(?:\.\d+)?\s?(?:kg|g|mg|mcg|km|m|cm|mm|L|mL|%|percent|"
    r"minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?|ft|feet|"
    r"dives?|meetings?|layers?)\b)",
    re.I,
)
CURRENCY_RE = re.compile(
    r"(?:\b(?:AUD|USD|NZD|IDR|dollars?|rupiah)\b|[$€£])", re.I
)
APPROX_RE = re.compile(
    r"\b(?:about|around|approximately|approx\.?|roughly|nearly|almost|"
    r"more than|less than|over|under|~)\b", re.I
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
        flagged = []
        currency_sources = []
        approximate_sources = []

        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            if not NUMBER_RE.search(text):
                continue
            source = rhee.safe_text(item.get("source"))
            entry = {
                "source": source,
                "currency": bool(CURRENCY_RE.search(text)),
                "approximate": bool(APPROX_RE.search(text)),
            }
            flagged.append(entry)
            if entry["currency"]:
                currency_sources.append(source)
            if entry["approximate"]:
                approximate_sources.append(source)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_number_unit_guard": "applied",
            "deep_recall_quantitative_source_count": len(flagged),
            "deep_recall_currency_source_count": len(currency_sources),
            "deep_recall_approximate_quantity_source_count": len(approximate_sources),
            "deep_recall_quantitative_source_preview": flagged[:50],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL NUMBER / UNIT FIDELITY GUARD",
            f"Retrieved quantitative evidence records={len(flagged)}; currency-bearing records={len(currency_sources)}; approximate-quantity records={len(approximate_sources)}.",
            "Keep every material number attached to the unit, currency, period and scope stated by the source.",
            "Do not silently turn AUD into USD, kg into lb, gross into net, annual into monthly, fortnightly into weekly, total into per-person, or an approximate value into an exact value.",
            "Preserve qualifiers such as about, nearly, approximately, more than, less than, around and ranges unless stronger evidence establishes a precise value.",
            "A bare '$' may be ambiguous across an international archive. Use the source's stated currency when available; if it is not established, preserve the ambiguity rather than guessing.",
            "Do not combine or compare quantities from different periods/bases as though directly equivalent unless the answer explicitly explains the adjustment.",
            "If a calculation or conversion is useful, distinguish the retrieved source number from the derived calculation and retain the original unit/currency alongside it.",
            "For conflicting quantities about the same fact, apply chronology, scope and correction rules before choosing a value.",
        ]
        if flagged:
            lines.append(
                "Sources requiring quantity-aware reading: " +
                ", ".join(item["source"] for item in flagged[:50])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer56_deep_recall_response_hygiene import install as install_response_hygiene
    install_response_hygiene(rhee)
