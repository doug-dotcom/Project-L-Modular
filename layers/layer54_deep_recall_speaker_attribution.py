"""Layer 54 — Deep Recall quoted-speaker attribution guard.

Doug's archive contains stories, copied messages and remembered dialogue. A
sentence inside quotation marks may have been spoken by another person. Because
the enclosing raw record is Doug-authored, naive provenance handling can
incorrectly attribute the quoted proposition to Doug himself.

This guard flags direct-speech / attribution patterns so composition preserves
who said what. Quoted text remains useful evidence about what Doug recorded; it
is not automatically Doug's own assertion or independent corroboration.
Ordinary Recall is unchanged.
"""
import re

QUOTE_RE = re.compile(r"[\"“][^\"”\n]{4,240}[\"”]")
ATTRIBUTION_RE = re.compile(
    r"\b(?:said|told me|asked|replied|responded|wrote|texted|messaged|"
    r"according to|he said|she said|they said|Dad said|Mum said|"
    r"doctor said|GP said|psychologist said|sponsor said|boss said)\b",
    re.I,
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
        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            has_quote = bool(QUOTE_RE.search(text))
            has_attribution = bool(ATTRIBUTION_RE.search(text))
            if has_quote or has_attribution:
                flagged.append({
                    "source": rhee.safe_text(item.get("source")),
                    "role": rhee.safe_text(item.get("role")).lower(),
                    "direct_quote": has_quote,
                    "speaker_attribution": has_attribution,
                })

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_speaker_attribution_guard": "applied",
            "deep_recall_speaker_attribution_flagged_count": len(flagged),
            "deep_recall_speaker_attribution_flagged": flagged[:50],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL QUOTED-SPEAKER ATTRIBUTION GUARD",
            f"Retrieved records with direct-quote or speaker-attribution cues={len(flagged)}.",
            "The author of a stored record and the speaker of a quoted proposition are not necessarily the same person.",
            "If Doug records 'Dad said X', the archive supports that Doug recorded Dad as saying X; do not rewrite X as Doug's own belief or statement.",
            "Copied texts, emails, messages, dialogue, professional advice and remembered speech must retain their attributed speaker when that attribution is available.",
            "A quotation embedded in a Doug-authored record is not independent corroboration of its proposition merely because Doug preserved it.",
            "When the speaker is unclear, use wording such as 'the retrieved record quotes...' or preserve the ambiguity rather than assigning the statement to the most plausible person.",
            "Doug's surrounding first-person commentary remains Doug-authored evidence; distinguish it from the embedded speech at the claim level.",
            "Do not infer that quoted speech is verbatim unless the source itself establishes that; it may be Doug's recollection or paraphrase.",
        ]
        if flagged:
            lines.append(
                "Sources requiring speaker-aware reading: " +
                ", ".join(item["source"] for item in flagged[:50])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
