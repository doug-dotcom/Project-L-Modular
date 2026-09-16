"""Layer 20 — gap-directed Deep Recall rescue.

For broad chronological Deep Recall, a large interval between years represented
in the retrieved evidence is a reason to search that interval again — not proof
that nothing is stored there. This layer performs a bounded, gap-directed rescue
pass over the full corpus before composition.

It never invents events, and recording timestamps are not used as event dates.
"""
import re

MAX_GAPS = 6
RAW_PER_GAP = 8
MEMORY_PER_GAP = 6
EXTRA_CHAR_BUDGET = 42000


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def broad_request(query):
        return bool(re.search(
            r"\b(?:complete|entire|whole|full|chronological|chronology|timeline|history|beginning|end|all|everything|across my life|life story)\b",
            rhee.safe_text(query).lower(),
        ))

    def years_in(text):
        out = set()
        for value in re.findall(r"\b(?:19|20)\d{2}\b", rhee.safe_text(text)):
            try:
                year = int(value)
            except ValueError:
                continue
            if 1900 <= year <= 2100:
                out.add(year)
        return out

    def subject(query):
        text = re.sub(r"(?i)\bdeep\s+recall\b", "", rhee.safe_text(query))
        return re.sub(r"\s+", " ", text).strip()

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query) or not broad_request(query):
            return result

        evidence = list(result.get("evidence") or [])
        represented = set()
        for item in evidence:
            represented.update(years_in(item.get("quote_source")))
        ordered = sorted(represented)
        gaps = []
        for left, right in zip(ordered, ordered[1:]):
            if right - left >= 4:
                gaps.append((right - left, left, right))
        gaps.sort(reverse=True)
        gaps = gaps[:MAX_GAPS]
        if not gaps:
            return result

        raw_rows = list(rhee.load_all_raw_catchall())
        memories = list(rhee.load_all_memories())
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        additions = []
        used = 0
        rescued = {}
        base = subject(query) or rhee.safe_text(query)

        for _, left, right in gaps:
            if used >= EXTRA_CHAR_BUDGET:
                break
            span = right - left
            probes = sorted({left + 1, right - 1, left + span // 2})
            gap_query = f"{base} " + " ".join(str(y) for y in probes) + " during between period stage transition"

            raw_scored = []
            for row in raw_rows:
                content = rhee.safe_text(row.get("content"))
                content_years = years_in(content)
                if not any(left < y < right for y in content_years):
                    continue
                score = rhee.calculate_raw_score(row, gap_query)
                if score > 0:
                    raw_scored.append((score, row))
            raw_scored.sort(key=lambda pair: pair[0], reverse=True)

            mem_scored = []
            for memory in memories:
                content = rhee.row_content(memory)
                content_years = years_in(content)
                if not any(left < y < right for y in content_years):
                    continue
                score = rhee.calculate_memory_score(memory, gap_query)
                if score > 0:
                    mem_scored.append((score, memory))
            mem_scored.sort(key=lambda pair: pair[0], reverse=True)

            added_here = 0
            for score, row in raw_scored[:RAW_PER_GAP]:
                row_id = row.get("id")
                source = f"raw_catchall:{row_id}" if row_id is not None else ""
                content = rhee.safe_text(row.get("content"))
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1600]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET:
                    break
                item = {"source": source, "quote_source": excerpt,
                        "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                        "created_at": rhee.safe_text(row.get("created_at")),
                        "deep_recall_gap": f"{left}-{right}", "deep_recall_gap_score": score}
                evidence.append(item); additions.append(item); seen.add(source)
                used += len(excerpt); added_here += 1

            for score, memory in mem_scored[:MEMORY_PER_GAP]:
                table = rhee.safe_text(memory.get("_table", "memory"))
                memory_id = memory.get("id")
                source = f"{table}:{memory_id}" if memory_id is not None else ""
                content = rhee.row_content(memory)
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1600]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET:
                    break
                item = {"source": source, "quote_source": excerpt,
                        "role": rhee.memory_source_role(memory),
                        "created_at": rhee.safe_text(memory.get("created_at")),
                        "raw_id": memory.get("raw_id"),
                        "deep_recall_gap": f"{left}-{right}", "deep_recall_gap_score": score}
                evidence.append(item); additions.append(item); seen.add(source)
                used += len(excerpt); added_here += 1
            rescued[f"{left}-{right}"] = added_here

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL GAP-RESCUE EVIDENCE",
                "These source-linked records were recovered by targeted searches inside large chronological intervals visible in the first evidence set.",
                "A rescued record is evidence, not proof that the interval is now complete. Apply normal provenance/conflict rules.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | GAP={item.get('deep_recall_gap')} | ROLE={rhee.safe_text(item.get('role')).upper()}")
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({"deep_recall_gap_rescue": "applied",
                        "deep_recall_gap_rescue_intervals": rescued,
                        "deep_recall_gap_rescue_added": len(additions),
                        "deep_recall_gap_rescue_chars": used})
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet

    from layers.layer21_deep_recall_anchor_followthrough import install as install_anchor_followthrough
    install_anchor_followthrough(rhee)
