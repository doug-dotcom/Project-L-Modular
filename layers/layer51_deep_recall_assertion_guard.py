"""Layer 51 — Deep Recall assertion / question contamination guard.

Doug's raw archive contains questions, tests, hypotheticals, quoted text and
assistant prompts as well as autobiographical assertions. A sentence appearing
in a Doug-authored record is not automatically a fact Doug asserted about
himself. In particular, a test such as "Did I work at X?" must not later become
evidence that he worked at X.

This composition guard marks user evidence containing strong non-assertion cues
for careful reading. It does not discard the record: answers, corrections and
surrounding context can still make it valuable. Ordinary Recall is unchanged.
"""
import re

QUESTION_RE = re.compile(r"\?")
HYPOTHETICAL_RE = re.compile(
    r"\b(?:what if|hypothetically|suppose|imagine|for example|e\.g\.|"
    r"if I had|if I were|would I|could I|might I|test question|testing your memory|"
    r"I am testing|I'm testing)\b", re.I
)
QUOTE_RE = re.compile(r"(?:^|\s)[\"“][^\"”]{8,}[\"”]")


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
            if rhee.safe_text(item.get("role")).lower() != "user":
                continue
            text = rhee.safe_text(item.get("quote_source"))
            cues = []
            if QUESTION_RE.search(text):
                cues.append("question")
            if HYPOTHETICAL_RE.search(text):
                cues.append("hypothetical_or_test")
            if QUOTE_RE.search(text):
                cues.append("quoted_text")
            if cues:
                flagged.append({
                    "source": rhee.safe_text(item.get("source")),
                    "cues": cues,
                })

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_assertion_guard": "applied",
            "deep_recall_assertion_guard_flagged_count": len(flagged),
            "deep_recall_assertion_guard_flagged": flagged[:40],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL ASSERTION / QUESTION CONTAMINATION GUARD",
            f"Doug-authored evidence records with question/hypothetical/quote cues={len(flagged)}.",
            "A user-authored record is primary evidence of what Doug wrote, but not every sentence inside it is an autobiographical assertion.",
            "Do not convert a question into a fact. 'Did I work at X?' is evidence that Doug asked the question, not that he worked at X.",
            "Do not convert a hypothetical, example, test prompt, quoted passage, joke or proposed scenario into a factual memory merely because Doug authored the message.",
            "Read surrounding context. A message may contain both a question and genuine factual assertions; preserve the supported assertions while withholding the unasserted proposition.",
            "Explicit corrections and direct first-person statements remain governed by the existing authority/conflict rules.",
            "When uncertain whether Doug asserted a proposition or merely asked/explored it, do not promote the proposition to autobiographical fact without corroborating evidence.",
        ]
        if flagged:
            lines.append(
                "Sources requiring assertion-level reading: " +
                ", ".join(item["source"] for item in flagged[:40])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
