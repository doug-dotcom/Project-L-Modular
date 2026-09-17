"""Layer 33 — explicit time-window Deep Recall rescue.

When Doug asks for a period such as "before 1999", "after 2010" or
"between 2000 and 2015", Deep Recall should actively look for evidence whose
content places events inside that requested period. Storage timestamps are never
used as event dates.

This is a retrieval rescue, not a chronology generator. Records still need to be
relevant to the recall subject and all provenance/conflict rules continue to
apply. Ordinary Recall is unchanged.
"""
import re

MAX_ADDITIONS = 28
CHAR_BUDGET = 42000


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def requested_window(query):
        text = rhee.safe_text(query).lower()
        between = re.search(r"\b(?:between|from)\s+((?:19|20)\d{2})\s+(?:and|to|through|until|-)\s*((?:19|20)\d{2})\b", text)
        if between:
            a, b = int(between.group(1)), int(between.group(2))
            return min(a, b), max(a, b), "range"

        before = re.search(r"\b(?:before|prior to|up to)\s+((?:19|20)\d{2})\b", text)
        if before:
            return 1900, int(before.group(1)) - 1, "before"

        after = re.search(r"\b(?:after|since|from)\s+((?:19|20)\d{2})\b", text)
        if after:
            return int(after.group(1)) + (1 if "after" in after.group(0) else 0), 2100, "after"

        years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", text)]
        if len(years) == 1:
            return years[0], years[0], "year"
        return None

    def content_years(text):
        return {int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", rhee.safe_text(text))}

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        window = requested_window(query)
        if not window:
            return result

        start, end, mode = window
        evidence = list(result.get("evidence") or [])
        seen = {rhee.safe_text(item.get("source")) for item in evidence}

        def in_window(text):
            return any(start <= year <= end for year in content_years(text))

        already = sum(1 for item in evidence if in_window(item.get("quote_source")))
        raw_scored = []
        for row in rhee.load_all_raw_catchall():
            content = rhee.safe_text(row.get("content"))
            if not content or not in_window(content):
                continue
            score = rhee.calculate_raw_score(row, query)
            if score > 0:
                raw_scored.append((score, row))
        raw_scored.sort(key=lambda pair: pair[0], reverse=True)

        mem_scored = []
        for memory in rhee.load_all_memories():
            content = rhee.row_content(memory)
            if not content or not in_window(content):
                continue
            score = rhee.calculate_memory_score(memory, query)
            if score > 0:
                mem_scored.append((score, memory))
        mem_scored.sort(key=lambda pair: pair[0], reverse=True)

        additions = []
        used = 0
        for score, row in raw_scored:
            if len(additions) >= MAX_ADDITIONS or used >= CHAR_BUDGET:
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
                "source": source, "quote_source": excerpt,
                "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_time_window": f"{start}-{end}",
                "deep_recall_time_window_score": score,
            }
            evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt)

        for score, memory in mem_scored:
            if len(additions) >= MAX_ADDITIONS or used >= CHAR_BUDGET:
                break
            table = rhee.safe_text(memory.get("_table", "memory"))
            memory_id = memory.get("id")
            source = f"{table}:{memory_id}" if memory_id is not None else ""
            content = rhee.row_content(memory)
            if not source or source in seen:
                continue
            excerpt = content[:1800]
            if used + len(excerpt) > CHAR_BUDGET:
                break
            item = {
                "source": source, "quote_source": excerpt,
                "role": rhee.memory_source_role(memory),
                "created_at": rhee.safe_text(memory.get("created_at")),
                "raw_id": memory.get("raw_id"),
                "deep_recall_time_window": f"{start}-{end}",
                "deep_recall_time_window_score": score,
            }
            evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL EXPLICIT TIME-WINDOW RESCUE",
                f"Requested event window: {start}-{end} ({mode}).",
                "These records were selected because their CONTENT contains a year inside the requested period and they are relevant to the query.",
                "created_at/storage timestamps were not used to decide event-period membership.",
                "A year appearing in a record is a retrieval lead; bind specific events to dates only when the evidence actually supports that relationship.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | WINDOW={item.get('deep_recall_time_window')} | ROLE={rhee.safe_text(item.get('role')).upper()}")
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)

        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_time_window_rescue": "applied",
            "deep_recall_time_window_start": start,
            "deep_recall_time_window_end": end,
            "deep_recall_time_window_mode": mode,
            "deep_recall_time_window_initial_sources": already,
            "deep_recall_time_window_added": len(additions),
            "deep_recall_time_window_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
