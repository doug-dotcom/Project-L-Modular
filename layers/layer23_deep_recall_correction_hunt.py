"""Layer 23 — explicit Deep Recall correction hunt.

A broad archive may contain an older autobiographical statement plus a later Doug
correction written with very different surrounding language. Deep Recall should
make a dedicated pass for relevant Doug-authored correction/clarification records
before composition so stale versions are less likely to survive unchallenged.

This layer never decides a conflict merely because a correction cue is present.
It adds the source-linked primary record; the existing authority/conflict policy
still determines whether it clearly supersedes the older fact.
"""
import re

MAX_CORRECTIONS = 20
CHAR_BUDGET = 28000

CORRECTION_RE = re.compile(
    r"\b(?:correction|corrected|actually|clarif(?:y|ied|ication)|to be clear|"
    r"not quite|that's wrong|that is wrong|was wrong|my mistake|i meant|"
    r"rather than|not .{0,40} but|update(?:d)?|supersed(?:e|ed|es))\b",
    re.IGNORECASE,
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
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        candidates = []

        for row in rhee.load_all_raw_catchall():
            if rhee.safe_text(row.get("role")).lower() != "user":
                continue
            content = rhee.safe_text(row.get("content"))
            if not content or not CORRECTION_RE.search(content):
                continue
            score = rhee.calculate_raw_score(row, query)
            if score > 0:
                candidates.append((score, row))

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        additions = []
        used = 0
        for score, row in candidates:
            if len(additions) >= MAX_CORRECTIONS or used >= CHAR_BUDGET:
                break
            row_id = row.get("id")
            source = f"raw_catchall:{row_id}" if row_id is not None else ""
            content = rhee.safe_text(row.get("content"))
            if not source or source in seen:
                continue
            excerpt = content[:1800]
            if used + len(excerpt) > CHAR_BUDGET:
                break
            item = {
                "source": source,
                "quote_source": excerpt,
                "role": "user",
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_correction_candidate": True,
                "deep_recall_correction_score": score,
            }
            evidence.append(item)
            additions.append(item)
            seen.add(source)
            used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL CORRECTION HUNT",
                "These Doug-authored records contain correction/clarification cues and are relevant to the recall subject.",
                "A cue alone does not prove supersession. Compare the actual facts and chronology under the existing evidence-authority rules.",
                "If a later Doug record clearly corrects the same fact, prefer the correction; otherwise preserve uncertainty/conflict.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | ROLE=USER | CREATED_AT={item.get('created_at', '')}")
                lines.append(item["quote_source"])
                lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_correction_hunt": "applied",
            "deep_recall_correction_candidates_added": len(additions),
            "deep_recall_correction_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
