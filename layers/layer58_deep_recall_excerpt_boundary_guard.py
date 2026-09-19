"""Layer 58 — Deep Recall excerpt-boundary integrity guard.

Testing exposed source excerpts that can end mid-sentence (for example a money
record ending in "...over 200 and thousand dol"). A correct source can therefore
become ambiguous or misleading simply because the evidence window was cut at a
fixed character boundary.

This layer detects likely clipped edges in the completed evidence packet and
adds a composition guard: never derive precision or complete a proposition from
a visibly truncated edge. Where possible, rely on a match-centred/full source
window already present; otherwise qualify or withhold the incomplete fragment.
It changes no stored memory and does not affect ordinary Recall.
"""
import re

TRAILING_COMPLETE_RE = re.compile(r'(?:[.!?][\"”’\')\]]?|\n\s*[-*]\s*[^\n]+[.!?]?)\s*$')
LEADING_FRAGMENT_RE = re.compile(r'^[a-z0-9,;:)\]]')


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def likely_trailing_clip(text):
        clean = rhee.safe_text(text).rstrip()
        if not clean or len(clean) < 250:
            return False
        if clean.endswith(("…", "...")):
            return True
        return not bool(TRAILING_COMPLETE_RE.search(clean))

    def likely_leading_clip(text):
        clean = rhee.safe_text(text).lstrip()
        return bool(clean) and bool(LEADING_FRAGMENT_RE.search(clean[:1]))

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        flagged = []
        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            trailing = likely_trailing_clip(text)
            leading = likely_leading_clip(text)
            if trailing or leading:
                flagged.append({
                    "source": rhee.safe_text(item.get("source")),
                    "leading_clip": leading,
                    "trailing_clip": trailing,
                })

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_excerpt_boundary_guard": "applied",
            "deep_recall_excerpt_boundary_flagged_count": len(flagged),
            "deep_recall_excerpt_boundary_flagged": flagged[:60],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL EXCERPT-BOUNDARY INTEGRITY GUARD",
            f"Evidence excerpts with possible clipped leading/trailing boundaries={len(flagged)}.",
            "A source can be relevant while its displayed excerpt is incomplete. Do not complete a cut-off sentence from plausibility or memory.",
            "Do not derive an exact number, currency, date, identity, negation, outcome or causal claim from text that visibly ends before the proposition is complete.",
            "If a match-centred or fuller window from the SAME source is present, use that fuller local context to resolve the fragment; it is still one source, not extra corroboration.",
            "If the missing edge cannot be recovered from evidence already supplied to composition, qualify the claim or omit the incomplete detail rather than guessing the missing words.",
            "A clipped excerpt is an evidence-presentation limitation, not evidence that the underlying source or memory is incomplete.",
            "Preserve source attribution even when withholding a detail because its retrieved excerpt is truncated.",
        ]
        if flagged:
            lines.append(
                "Sources requiring boundary-aware reading: " +
                ", ".join(item["source"] for item in flagged[:60])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
