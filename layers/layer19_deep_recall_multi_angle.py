"""Layer 19 — multi-angle Deep Recall.

A full-corpus scan can still rank evidence too narrowly if every record is scored
against only one wording of Doug's question. Explicit Deep Recall therefore
re-scores the already available full corpus from several evidence-seeking angles
and adds distinct source-linked records that the first ranking may have missed.

This is deliberately slower than Recall. It never creates facts and never treats
an empty angle as proof that a memory is absent.
"""
import re

RAW_PER_ANGLE = 12
MEMORY_PER_ANGLE = 10
EXTRA_CHAR_BUDGET = 50000


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def subject(query):
        text = rhee.safe_text(query)
        text = re.sub(r"(?i)\bdeep\s+recall\b", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def angles(query):
        base = subject(query) or rhee.safe_text(query)
        return [
            ("chronology", f"{base} dates years chronology stages transitions before after timeline"),
            ("entities", f"{base} people names places schools employers organisations businesses relationships"),
            ("primary_corrections", f"{base} Doug said corrected correction clarification original first person primary evidence contradiction"),
        ]

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        additions = []
        used = 0
        angle_counts = {}

        raw_rows = list(rhee.load_all_raw_catchall())
        memories = list(rhee.load_all_memories())

        for angle_name, angle_query in angles(query):
            raw_scored = []
            for row in raw_rows:
                score = rhee.calculate_raw_score(row, angle_query)
                if score > 0:
                    raw_scored.append((score, row))
            raw_scored.sort(key=lambda pair: pair[0], reverse=True)

            memory_scored = []
            for memory in memories:
                score = rhee.calculate_memory_score(memory, angle_query)
                if score > 0:
                    memory_scored.append((score, memory))
            memory_scored.sort(key=lambda pair: pair[0], reverse=True)

            added_here = 0
            for score, row in raw_scored[:RAW_PER_ANGLE]:
                if used >= EXTRA_CHAR_BUDGET:
                    break
                row_id = row.get("id")
                source = f"raw_catchall:{row_id}" if row_id is not None else ""
                content = rhee.safe_text(row.get("content"))
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1400]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET:
                    break
                item = {"source": source, "quote_source": excerpt,
                        "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                        "created_at": rhee.safe_text(row.get("created_at")),
                        "deep_recall_angle": angle_name, "deep_recall_angle_score": score}
                evidence.append(item); additions.append(item); seen.add(source)
                used += len(excerpt); added_here += 1

            for score, memory in memory_scored[:MEMORY_PER_ANGLE]:
                if used >= EXTRA_CHAR_BUDGET:
                    break
                table = rhee.safe_text(memory.get("_table", "memory"))
                memory_id = memory.get("id")
                source = f"{table}:{memory_id}" if memory_id is not None else ""
                content = rhee.row_content(memory)
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1400]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET:
                    break
                item = {"source": source, "quote_source": excerpt,
                        "role": rhee.memory_source_role(memory),
                        "created_at": rhee.safe_text(memory.get("created_at")),
                        "raw_id": memory.get("raw_id"),
                        "deep_recall_angle": angle_name, "deep_recall_angle_score": score}
                evidence.append(item); additions.append(item); seen.add(source)
                used += len(excerpt); added_here += 1
            angle_counts[angle_name] = added_here

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = ["DEEP RECALL MULTI-ANGLE EVIDENCE",
                     "These distinct records were recovered by rescoring the full corpus from complementary angles.",
                     "They are ordinary source-linked evidence: apply the existing provenance, conflict and chronology rules.",
                     "Do not assume an angle is complete merely because it returned records.", ""]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | ANGLE={item.get('deep_recall_angle')} | ROLE={rhee.safe_text(item.get('role')).upper()} | CREATED_AT={item.get('created_at', '')}")
                lines.append(rhee.safe_text(item.get("quote_source"))); lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({"deep_recall_multi_angle": "applied",
                        "deep_recall_multi_angle_added": len(additions),
                        "deep_recall_multi_angle_chars": used,
                        "deep_recall_multi_angle_counts": angle_counts})
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet

    from layers.layer20_deep_recall_gap_rescue import install as install_gap_rescue
    install_gap_rescue(rhee)
