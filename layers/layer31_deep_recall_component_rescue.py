"""Layer 31 — component-directed Deep Recall rescue.

Layer 30 decomposes explicit compound Deep Recall requests into requested parts.
This layer checks whether each part has meaningful evidence representation and,
when a part is thin, performs a targeted full-corpus rescue for that exact part.

It never invents subquestions or facts. A rescue miss means only that the current
retrieval did not establish that component; it is not proof the memory is absent.
Ordinary Recall is unchanged.
"""

RAW_PER_PART = 8
MEMORY_PER_PART = 6
MAX_THIN_PARTS = 5
EXTRA_CHAR_BUDGET = 42000
MIN_SUPPORTING_ITEMS = 2


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def score_item(item, part):
        text = rhee.safe_text(item.get("quote_source"))
        if not text:
            return 0
        # Use the same semantic/lexical scorer family already governing Rhee.
        # A lightweight synthetic row lets us assess packet coverage without
        # changing the stored evidence.
        row = {"content": text, "role": item.get("role", "unknown")}
        try:
            return rhee.calculate_raw_score(row, part)
        except Exception:
            return 0

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        plan = dict(result.get("recall_plan") or {})
        parts = list(plan.get("deep_recall_question_parts") or [])
        if len(parts) <= 1:
            return result

        evidence = list(result.get("evidence") or [])
        coverage = {}
        thin_parts = []
        for part in parts:
            supporting = sum(1 for item in evidence if score_item(item, part) > 0)
            coverage[part] = supporting
            if supporting < MIN_SUPPORTING_ITEMS:
                thin_parts.append(part)

        thin_parts = thin_parts[:MAX_THIN_PARTS]
        if not thin_parts:
            output = dict(result)
            plan.update({
                "deep_recall_component_rescue": "not_needed",
                "deep_recall_component_initial_coverage": coverage,
                "deep_recall_component_thin_parts": [],
            })
            output["recall_plan"] = plan
            return output

        raw_rows = list(rhee.load_all_raw_catchall())
        memories = list(rhee.load_all_memories())
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        additions = []
        used = 0
        rescued = {}

        for part in thin_parts:
            if used >= EXTRA_CHAR_BUDGET:
                break
            raw_scored = []
            for row in raw_rows:
                score = rhee.calculate_raw_score(row, part)
                if score > 0:
                    raw_scored.append((score, row))
            raw_scored.sort(key=lambda pair: pair[0], reverse=True)

            mem_scored = []
            for memory in memories:
                score = rhee.calculate_memory_score(memory, part)
                if score > 0:
                    mem_scored.append((score, memory))
            mem_scored.sort(key=lambda pair: pair[0], reverse=True)

            added_here = 0
            for score, row in raw_scored[:RAW_PER_PART]:
                row_id = row.get("id")
                source = f"raw_catchall:{row_id}" if row_id is not None else ""
                content = rhee.safe_text(row.get("content"))
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1600]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET:
                    break
                item = {
                    "source": source,
                    "quote_source": excerpt,
                    "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                    "created_at": rhee.safe_text(row.get("created_at")),
                    "deep_recall_component": part,
                    "deep_recall_component_score": score,
                }
                evidence.append(item); additions.append(item); seen.add(source)
                used += len(excerpt); added_here += 1

            for score, memory in mem_scored[:MEMORY_PER_PART]:
                table = rhee.safe_text(memory.get("_table", "memory"))
                memory_id = memory.get("id")
                source = f"{table}:{memory_id}" if memory_id is not None else ""
                content = rhee.row_content(memory)
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1600]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET:
                    break
                item = {
                    "source": source,
                    "quote_source": excerpt,
                    "role": rhee.memory_source_role(memory),
                    "created_at": rhee.safe_text(memory.get("created_at")),
                    "raw_id": memory.get("raw_id"),
                    "deep_recall_component": part,
                    "deep_recall_component_score": score,
                }
                evidence.append(item); additions.append(item); seen.add(source)
                used += len(excerpt); added_here += 1
            rescued[part] = added_here

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL COMPONENT-RESCUE EVIDENCE",
                "These source-linked records were recovered because an explicit part of Doug's compound request was thin in the first evidence packet.",
                "Use them only for the component they genuinely support and under all existing provenance/conflict rules.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | COMPONENT={item.get('deep_recall_component')} | ROLE={rhee.safe_text(item.get('role')).upper()}")
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        plan.update({
            "deep_recall_component_rescue": "applied",
            "deep_recall_component_initial_coverage": coverage,
            "deep_recall_component_thin_parts": thin_parts,
            "deep_recall_component_rescued": rescued,
            "deep_recall_component_added": len(additions),
            "deep_recall_component_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
