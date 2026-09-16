"""Layer 21 — evidence-led anchor follow-through for explicit Deep Recall.

Deep Recall can recover a useful record containing a person, employer, school,
place or organisation that Doug did not name in the query. That newly recovered
anchor can lead to other relevant records. This layer follows a small set of
high-signal anchors found in retrieved evidence back through the full corpus.

It never creates facts. Anchors only cause additional source-linked records to
be considered; normal provenance, conflict and chronology rules still apply.
"""
import re
from collections import Counter

MAX_ANCHORS = 10
RAW_PER_ANCHOR = 4
MEMORY_PER_ANCHOR = 3
EXTRA_CHAR_BUDGET = 36000

STOP_ANCHORS = {
    "Doug", "Deep Recall", "Recall", "Source", "User", "Assistant", "Project",
    "Memory", "Today", "Evidence", "Layer", "Supabase", "ChatGPT", "Rhee",
    "The", "This", "That", "There", "Then", "When", "Where", "What", "Your",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def subject(query):
        text = re.sub(r"(?i)\bdeep\s+recall\b", "", rhee.safe_text(query))
        return re.sub(r"\s+", " ", text).strip()

    def anchors_from(evidence, query):
        query_lower = rhee.safe_text(query).lower()
        counts = Counter()
        for item in evidence[:80]:
            text = rhee.safe_text(item.get("quote_source"))
            candidates = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\b|\b[A-Z]{2,8}\b", text)
            for candidate in candidates:
                candidate = candidate.strip()
                if candidate in STOP_ANCHORS or candidate.lower() in query_lower:
                    continue
                if len(candidate) < 3 or candidate.isdigit():
                    continue
                counts[candidate] += 1
        ranked = sorted(counts.items(), key=lambda pair: (pair[1], len(pair[0])), reverse=True)
        return [name for name, _ in ranked[:MAX_ANCHORS]]

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        anchors = anchors_from(evidence, query)
        if not anchors:
            return result

        raw_rows = list(rhee.load_all_raw_catchall())
        memories = list(rhee.load_all_memories())
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        additions = []
        used = 0
        anchor_counts = {}
        base = subject(query) or rhee.safe_text(query)

        for anchor in anchors:
            if used >= EXTRA_CHAR_BUDGET:
                break
            angle_query = f"{base} {anchor}"
            anchor_lower = anchor.lower()
            raw_scored = []
            for row in raw_rows:
                content = rhee.safe_text(row.get("content"))
                if anchor_lower not in content.lower():
                    continue
                score = rhee.calculate_raw_score(row, angle_query)
                if score > 0:
                    raw_scored.append((score, row))
            raw_scored.sort(key=lambda pair: pair[0], reverse=True)
            mem_scored = []
            for memory in memories:
                content = rhee.row_content(memory)
                if anchor_lower not in content.lower():
                    continue
                score = rhee.calculate_memory_score(memory, angle_query)
                if score > 0:
                    mem_scored.append((score, memory))
            mem_scored.sort(key=lambda pair: pair[0], reverse=True)
            added_here = 0
            for score, row in raw_scored[:RAW_PER_ANCHOR]:
                row_id = row.get("id"); source = f"raw_catchall:{row_id}" if row_id is not None else ""; content = rhee.safe_text(row.get("content"))
                if not source or source in seen or not content: continue
                excerpt = content[:1500]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET: break
                item = {"source": source, "quote_source": excerpt, "role": rhee.safe_text(row.get("role", "unknown")).lower(), "created_at": rhee.safe_text(row.get("created_at")), "deep_recall_anchor": anchor, "deep_recall_anchor_score": score}
                evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt); added_here += 1
            for score, memory in mem_scored[:MEMORY_PER_ANCHOR]:
                table = rhee.safe_text(memory.get("_table", "memory")); memory_id = memory.get("id"); source = f"{table}:{memory_id}" if memory_id is not None else ""; content = rhee.row_content(memory)
                if not source or source in seen or not content: continue
                excerpt = content[:1500]
                if used + len(excerpt) > EXTRA_CHAR_BUDGET: break
                item = {"source": source, "quote_source": excerpt, "role": rhee.memory_source_role(memory), "created_at": rhee.safe_text(memory.get("created_at")), "raw_id": memory.get("raw_id"), "deep_recall_anchor": anchor, "deep_recall_anchor_score": score}
                evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt); added_here += 1
            anchor_counts[anchor] = added_here

        output = dict(result); output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = ["DEEP RECALL EVIDENCE-LED FOLLOW-THROUGH", "These records were found by following named anchors discovered in already-retrieved evidence.", "An anchor is a search lead, not a fact by itself. Use only the source-linked content as evidence.", ""]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | ANCHOR={item.get('deep_recall_anchor')} | ROLE={rhee.safe_text(item.get('role')).upper()}"); lines.append(rhee.safe_text(item.get("quote_source"))); lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context; output["context_size"] = len(context); output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        receipt = dict(output.get("recall_plan") or {}); receipt.update({"deep_recall_anchor_followthrough": "applied", "deep_recall_anchors_followed": anchors, "deep_recall_anchor_counts": anchor_counts, "deep_recall_anchor_added": len(additions), "deep_recall_anchor_chars": used}); output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet

    from layers.layer22_deep_recall_saturation_stop import install as install_saturation_stop
    install_saturation_stop(rhee)
