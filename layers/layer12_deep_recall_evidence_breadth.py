"""Layer 12 — deep-recall evidence breadth.

Layer 11 makes explicit "deep recall" inspect the full corpus. Layer 12 makes
sure the answer is not then squeezed back through ordinary recall's tiny output
window. Deep recall may be slower and larger by design: select a broad,
diversified set of relevant evidence after the full scan, while ordinary
"recall" remains fast and bounded.

This layer never creates facts. It only adds relevant source-linked evidence
already present in raw_catchall or governed memory tables.
"""

RAW_LIMIT = 60
MEMORY_LIMIT = 50
TOTAL_CHAR_BUDGET = 120000
PER_TABLE_LIMIT = 12


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        text = rhee.safe_text(query).lower()
        return rhee.term_in_text("deep recall", text) and "career stage" not in text

    def key(item):
        return (rhee.safe_text(item.get("source")), rhee.safe_text(item.get("quote_source")))

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        merged = list(result.get("evidence") or [])
        seen = {key(item) for item in merged}
        used_chars = sum(len(rhee.safe_text(item.get("quote_source"))) for item in merged)

        # Layer 11 has already loaded these corpora; normal process caches make
        # this second pass cheap. Re-score the complete corpus for the exact
        # user query, then diversify what is allowed into the model context.
        raw_scored = []
        for row in rhee.load_all_raw_catchall():
            score = rhee.calculate_raw_score(row, query)
            if score > 0:
                raw_scored.append((score, row))
        raw_scored.sort(key=lambda pair: pair[0], reverse=True)

        memory_scored = []
        for memory in rhee.load_all_memories():
            score = rhee.calculate_memory_score(memory, query)
            if score > 0:
                memory_scored.append((score, memory))
        memory_scored.sort(key=lambda pair: pair[0], reverse=True)

        added_raw = 0
        for score, row in raw_scored:
            if added_raw >= RAW_LIMIT or used_chars >= TOTAL_CHAR_BUDGET:
                break
            row_id = row.get("id")
            content = rhee.safe_text(row.get("content"))
            if row_id is None or not content:
                continue
            excerpt = content[:1200]
            item = {
                "source": f"raw_catchall:{row_id}",
                "quote_source": excerpt,
                "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_score": score,
            }
            item_key = key(item)
            if item_key in seen:
                continue
            if used_chars + len(excerpt) > TOTAL_CHAR_BUDGET:
                break
            merged.append(item)
            seen.add(item_key)
            used_chars += len(excerpt)
            added_raw += 1

        added_memory = 0
        per_table = {}
        for score, memory in memory_scored:
            if added_memory >= MEMORY_LIMIT or used_chars >= TOTAL_CHAR_BUDGET:
                break
            table = rhee.safe_text(memory.get("_table", "memory"))
            if per_table.get(table, 0) >= PER_TABLE_LIMIT:
                continue
            memory_id = memory.get("id")
            content = rhee.row_content(memory)
            if memory_id is None or not content:
                continue
            excerpt = content[:1400]
            item = {
                "source": f"{table}:{memory_id}",
                "quote_source": excerpt,
                "role": rhee.memory_source_role(memory),
                "created_at": rhee.safe_text(memory.get("created_at")),
                "raw_id": memory.get("raw_id"),
                "deep_recall_score": score,
            }
            item_key = key(item)
            if item_key in seen:
                continue
            if used_chars + len(excerpt) > TOTAL_CHAR_BUDGET:
                break
            merged.append(item)
            seen.add(item_key)
            used_chars += len(excerpt)
            added_memory += 1
            per_table[table] = per_table.get(table, 0) + 1

        context = rhee.safe_text(result.get("context"))
        additions = [item for item in merged if key(item) not in {key(old) for old in (result.get("evidence") or [])}]
        if additions:
            lines = [
                "DEEP RECALL BREADTH PASS",
                "The following source-linked extracts were selected only after full-corpus inspection.",
                "Use them with the same provenance/conflict rules as the primary recall packet.",
                "Do not treat absence from this selected set as proof that a memory is not stored.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item.get('source')} | ROLE={rhee.safe_text(item.get('role')).upper()} | CREATED_AT={item.get('created_at', '')}")
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)

        output = dict(result)
        output["evidence"] = merged
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(merged) or bool(result.get("recall_active"))
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({
            "deep_recall_breadth": "expanded",
            "deep_recall_raw_added": added_raw,
            "deep_recall_memory_added": added_memory,
            "deep_recall_evidence_sources": len(merged),
            "deep_recall_evidence_chars": used_chars,
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet
