"""Layer 18 — deep-recall completeness ledger.

Deep Recall already scans broadly and self-audits. This layer gives the model a
compact evidence ledger before composition so broad historical answers can see
whether the retrieved packet spans the chronology/source types implied by the
question. It does not invent missing periods or treat a gap as proof that no
memory exists.
"""
import re
from collections import Counter


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def source_family(source):
        value = rhee.safe_text(source)
        return value.split(":", 1)[0] if ":" in value else value

    def event_years(text):
        years = set()
        for match in re.findall(r"\b(?:19|20)\d{2}\b", rhee.safe_text(text)):
            try:
                year = int(match)
            except ValueError:
                continue
            if 1900 <= year <= 2100:
                years.add(year)
        return years

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        families = Counter()
        roles = Counter()
        years = set()
        primary = 0

        for item in evidence:
            families[source_family(item.get("source"))] += 1
            role = rhee.safe_text(item.get("role")).lower() or "unknown"
            roles[role] += 1
            if role == "user":
                primary += 1
            years.update(event_years(item.get("quote_source")))

        ordered_years = sorted(years)
        gaps = []
        for left, right in zip(ordered_years, ordered_years[1:]):
            if right - left >= 4:
                gaps.append((left, right, right - left))

        broad = bool(re.search(
            r"\b(?:complete|entire|whole|full|chronological|chronology|timeline|history|"
            r"beginning|end|all|everything|across my life|life story)\b",
            rhee.safe_text(query).lower(),
        ))

        ledger_lines = [
            "DEEP RECALL COMPLETENESS LEDGER",
            f"Evidence sources available to composition: {len(evidence)}.",
            f"Doug-authored primary sources: {primary}.",
            "Source families: " + (", ".join(f"{k}={v}" for k, v in families.most_common()) or "none"),
            "Evidence roles: " + (", ".join(f"{k}={v}" for k, v in roles.most_common()) or "none"),
            "Years explicitly mentioned inside retrieved evidence: " + (
                ", ".join(str(y) for y in ordered_years) if ordered_years else "none"
            ),
        ]
        if gaps:
            ledger_lines.append(
                "Large year intervals visible between mentioned years: " +
                ", ".join(f"{a}-{b}" for a, b, _ in gaps[:12]) + "."
            )
        if broad:
            ledger_lines.extend([
                "This is a broad/chronological request. Before answering, compare the requested scope with this ledger and the retrieved evidence.",
                "A sparse interval is a prompt to be cautious and explicit about coverage; it is NOT proof that nothing happened or that no memory is stored.",
                "Do not claim completeness merely because many records were retrieved. Prefer an evidence-supported chronology and name genuinely thin periods.",
            ])
        else:
            ledger_lines.append(
                "Use this ledger only as a coverage aid; do not expand a focused question into an unnecessary life-history answer."
            )

        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(ledger_lines)
        output["context"] = context
        output["context_size"] = len(context)
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({
            "deep_recall_completeness_ledger": "applied",
            "deep_recall_ledger_sources": len(evidence),
            "deep_recall_ledger_primary_sources": primary,
            "deep_recall_ledger_year_count": len(ordered_years),
            "deep_recall_ledger_large_year_gaps": gaps[:12],
            "deep_recall_ledger_broad_request": broad,
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet

    from layers.layer19_deep_recall_multi_angle import install as install_multi_angle
    install_multi_angle(rhee)
