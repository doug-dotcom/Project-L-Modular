"""Layer 64 — Deep Recall contradiction-targeted rescue.

Final conflict reconciliation can identify that two retrieved records may differ,
and Layer 60 distinguishes same-event from different-event date differences.
When a genuine or plausible same-fact conflict remains, Deep Recall should make
one last targeted attempt to find a primary clarification/correction before
surfacing the conflict unresolved.

This layer uses conflict/correction cues already present in the completed packet
as retrieval leads, searches Doug-authored raw records for matching named/date
anchors plus correction language, and adds only distinct source-linked records.
It never auto-resolves a conflict and ordinary Recall is unchanged.
"""
import re

MAX_ADDITIONS = 16
CHAR_BUDGET = 26000

CORRECTION_RE = re.compile(
    r"\b(?:actually|correction|corrected|to be clear|I meant|that was wrong|"
    r"not\s+[^.!?\n]{1,80}\s+but|rather than|instead|mistake|"
    r"changed|updated|clarif(?:y|ied|ication))\b",
    re.I,
)
ANCHOR_RE = re.compile(
    r"\b(?:(?:19|20)\d{2}|[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}|[A-Z]{2,8})\b"
)
STOP = {
    "Doug", "Deep Recall", "Source", "User", "Assistant", "The", "This", "That",
    "There", "When", "Where", "What", "Project", "Evidence",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})

        cue_sources = list(
            plan.get("deep_recall_final_conflict_cue_sources") or []
        )
        if not cue_sources:
            output = dict(result)
            plan["deep_recall_conflict_targeted_rescue"] = "not_needed"
            plan["deep_recall_conflict_targeted_added"] = 0
            output["recall_plan"] = plan
            return output

        cue_set = set(cue_sources)
        anchors = []
        seen_anchor = set()
        for item in evidence:
            if rhee.safe_text(item.get("source")) not in cue_set:
                continue
            text = rhee.safe_text(item.get("quote_source"))
            for anchor in ANCHOR_RE.findall(text):
                anchor = anchor.strip()
                if anchor in STOP or anchor in seen_anchor:
                    continue
                anchors.append(anchor)
                seen_anchor.add(anchor)
                if len(anchors) >= 18:
                    break
            if len(anchors) >= 18:
                break

        if not anchors:
            output = dict(result)
            plan["deep_recall_conflict_targeted_rescue"] = "no_anchors"
            plan["deep_recall_conflict_targeted_added"] = 0
            output["recall_plan"] = plan
            return output

        seen_sources = {rhee.safe_text(item.get("source")) for item in evidence}
        scored = []
        query_lower = rhee.safe_text(query).lower()

        for row in rhee.load_all_raw_catchall():
            role = rhee.safe_text(row.get("role")).lower()
            if role != "user":
                continue
            content = rhee.safe_text(row.get("content"))
            if not content or not CORRECTION_RE.search(content):
                continue
            low = content.lower()
            matched = [a for a in anchors if a.lower() in low]
            if not matched:
                continue
            try:
                score = rhee.calculate_raw_score(row, query)
            except Exception:
                score = 0
            # Correction + discovered anchor is the gate; score ranks candidates.
            scored.append((score, len(matched), row, matched))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        additions = []
        used = 0
        for score, _, row, matched in scored:
            if len(additions) >= MAX_ADDITIONS or used >= CHAR_BUDGET:
                break
            row_id = row.get("id")
            source = f"raw_catchall:{row_id}" if row_id is not None else ""
            if not source or source in seen_sources:
                continue
            content = rhee.safe_text(row.get("content"))
            excerpt = content[:1800]
            if used + len(excerpt) > CHAR_BUDGET:
                break
            item = {
                "source": source,
                "quote_source": excerpt,
                "role": "user",
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_conflict_rescue": True,
                "deep_recall_conflict_rescue_anchors": matched[:8],
                "deep_recall_conflict_rescue_score": score,
            }
            evidence.append(item)
            additions.append(item)
            seen_sources.add(source)
            used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        plan.update({
            "deep_recall_conflict_targeted_rescue":
                "applied" if additions else "searched_no_new_sources",
            "deep_recall_conflict_targeted_anchors": anchors,
            "deep_recall_conflict_targeted_added": len(additions),
            "deep_recall_conflict_targeted_chars": used,
        })
        output["recall_plan"] = plan

        if additions:
            lines = [
                "DEEP RECALL CONTRADICTION-TARGETED RESCUE",
                "These Doug-authored records were recovered because the completed packet contained correction/conflict cues and matching anchors.",
                "They are candidate clarification evidence only. Do not auto-resolve the conflict; compare the exact proposition, event identity, date scope and correction wording.",
                "",
            ]
            for item in additions:
                lines.append(
                    f"SOURCE {item['source']} | CONFLICT_RESCUE=YES | "
                    f"ANCHORS={', '.join(item.get('deep_recall_conflict_rescue_anchors') or [])}"
                )
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
            output["context"] = context
            output["context_size"] = len(context)

        return output

    rhee.build_context_packet = packet

    from layers.layer65_deep_recall_evidence_freeze import install as install_evidence_freeze
    install_evidence_freeze(rhee)
