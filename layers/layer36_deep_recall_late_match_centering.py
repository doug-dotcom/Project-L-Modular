"""Layer 36 — late-pass match-centred evidence windows.

Earlier match-centring protects long records found in the first Deep Recall pass,
but later rescue layers can add new long records after that centring has already
run. Those late records were being represented by their first 1.5-1.8k chars,
which can recreate the original "right document, wrong excerpt" failure.

This final rescue pass re-opens late-added source records and adds a compact
window around query-relevant text. It does not alter the source, invent facts or
affect ordinary Recall.
"""
import re

WINDOW = 2200
MAX_WINDOWS = 30
CHAR_BUDGET = 52000

LATE_KEYS = (
    "deep_recall_component", "deep_recall_provenance_backfill",
    "deep_recall_time_window", "deep_recall_alias",
    "deep_recall_transition", "deep_recall_angle",
    "deep_recall_gap", "deep_recall_anchor",
    "deep_recall_correction_candidate",
)

STOP = {
    "deep", "recall", "please", "take", "your", "time", "search", "everything",
    "have", "about", "what", "know", "complete", "entire", "whole", "full",
    "summarise", "summarize", "chronologically", "chronological", "history",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def terms(query):
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]{2,}", rhee.safe_text(query).lower())
        out = []
        seen = set()
        for word in words:
            if word in STOP or word in seen:
                continue
            out.append(word); seen.add(word)
        return out[:24]

    def centred(text, needles):
        low = text.lower()
        positions = [low.find(term) for term in needles if low.find(term) >= 0]
        if not positions:
            return ""
        centre = min(positions)
        start = max(0, centre - WINDOW // 3)
        end = min(len(text), start + WINDOW)
        start = max(0, end - WINDOW)
        return text[start:end].strip()

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        late = [item for item in evidence if any(item.get(key) for key in LATE_KEYS)]
        if not late:
            return result

        raw_index = {}
        memory_index = {}
        wanted_sources = {rhee.safe_text(item.get("source")) for item in late}

        for row in rhee.load_all_raw_catchall():
            source = f"raw_catchall:{row.get('id')}" if row.get("id") is not None else ""
            if source in wanted_sources:
                raw_index[source] = rhee.safe_text(row.get("content"))

        for memory in rhee.load_all_memories():
            table = rhee.safe_text(memory.get("_table", "memory"))
            source = f"{table}:{memory.get('id')}" if memory.get("id") is not None else ""
            if source in wanted_sources:
                memory_index[source] = rhee.row_content(memory)

        needles = terms(query)
        windows = []
        used = 0
        seen = set()

        for item in late:
            if len(windows) >= MAX_WINDOWS or used >= CHAR_BUDGET:
                break
            source = rhee.safe_text(item.get("source"))
            if not source or source in seen:
                continue
            full = raw_index.get(source) or memory_index.get(source) or ""
            if len(full) <= len(rhee.safe_text(item.get("quote_source"))) + 200:
                continue

            local_needles = list(needles)
            for key in ("deep_recall_component", "deep_recall_alias", "deep_recall_time_window"):
                value = rhee.safe_text(item.get(key)).lower()
                local_needles.extend(
                    token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]{2,}", value)
                    if token not in STOP
                )
            if item.get("deep_recall_transition"):
                local_needles.extend(["started", "began", "joined", "left", "moved", "changed", "ended", "returned", "retired"])

            window = centred(full, local_needles)
            if not window:
                continue
            original = rhee.safe_text(item.get("quote_source"))
            if window in original or original in window:
                continue
            if used + len(window) > CHAR_BUDGET:
                break
            windows.append((source, window))
            seen.add(source)
            used += len(window)

        if not windows:
            output = dict(result)
            plan = dict(output.get("recall_plan") or {})
            plan.update({
                "deep_recall_late_match_centering": "not_needed",
                "deep_recall_late_match_windows": 0,
            })
            output["recall_plan"] = plan
            return output

        lines = [
            "DEEP RECALL LATE-PASS MATCH-CENTRED WINDOWS",
            "These are additional windows from late-rescued long records, centred near the requested subject rather than blindly showing only the start of the record.",
            "They are excerpts from the SAME cited sources, not independent evidence.",
            "",
        ]
        for source, window in windows:
            lines.append(f"SOURCE {source} | MATCH_WINDOW=YES")
            lines.append(window)
            lines.append("")

        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_late_match_centering": "applied",
            "deep_recall_late_match_windows": len(windows),
            "deep_recall_late_match_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet

    from layers.layer37_deep_recall_final_receipt import install as install_final_receipt
    install_final_receipt(rhee)
