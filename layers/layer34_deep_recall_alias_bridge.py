"""Layer 34 — Deep Recall evidence-discovered alias bridge.

People, places and organisations can appear under different names across a long
archive: a relationship label in one record, a proper name in another, an
abbreviation elsewhere. Deep Recall should be able to use aliases that the
retrieved evidence itself explicitly links, without relying on a permanently
hard-coded synonym list.

This layer extracts only high-confidence alias/name links stated in retrieved
evidence, then uses those aliases as additional full-corpus retrieval leads.
Aliases are search leads, never facts by themselves. Ordinary Recall is unchanged.
"""
import re
from collections import Counter

MAX_ALIASES = 10
RAW_PER_ALIAS = 4
MEMORY_PER_ALIAS = 3
CHAR_BUDGET = 32000

PATTERNS = [
    re.compile(r"\b(?:my\s+)?(mum|mom|mother|dad|father|brother|sister|wife|husband|partner|fianc[eé]e?|friend|sponsor)\s*[,—:-]?\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b"),
    re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\s*\(([^)\n]{2,40})\)"),
    re.compile(r"\b([A-Z][A-Za-z0-9&.'-]{2,}(?:\s+[A-Z][A-Za-z0-9&.'-]{2,}){0,3})\s+(?:also known as|aka|formerly|previously called)\s+([A-Z][A-Za-z0-9&.'-]{2,}(?:\s+[A-Z][A-Za-z0-9&.'-]{2,}){0,3})\b", re.I),
]


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def discover(evidence):
        counts = Counter()
        examples = {}
        for item in evidence[:120]:
            text = rhee.safe_text(item.get("quote_source"))
            for pattern in PATTERNS:
                for match in pattern.finditer(text):
                    left = match.group(1).strip()
                    right = match.group(2).strip()
                    if not left or not right or left.lower() == right.lower():
                        continue
                    pair = (left, right)
                    counts[pair] += 1
                    examples[pair] = rhee.safe_text(item.get("source"))
        ranked = sorted(counts.items(), key=lambda p: (p[1], len(p[0][1])), reverse=True)
        return [(pair[0], pair[1], examples.get(pair, "")) for pair, _ in ranked[:MAX_ALIASES]]

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        aliases = discover(evidence)
        if not aliases:
            output = dict(result)
            plan = dict(output.get("recall_plan") or {})
            plan.update({"deep_recall_alias_bridge": "no_links_found", "deep_recall_alias_added": 0})
            output["recall_plan"] = plan
            return output

        raw_rows = list(rhee.load_all_raw_catchall())
        memories = list(rhee.load_all_memories())
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        additions = []
        used = 0
        followed = []

        for left, right, discovered_in in aliases:
            if used >= CHAR_BUDGET:
                break
            alias_query = f"{query} {left} {right}"
            tokens = {left.lower(), right.lower()}
            followed.append({"left": left, "right": right, "source": discovered_in})

            raw_scored = []
            for row in raw_rows:
                content = rhee.safe_text(row.get("content"))
                low = content.lower()
                if not any(token in low for token in tokens):
                    continue
                score = rhee.calculate_raw_score(row, alias_query)
                if score > 0:
                    raw_scored.append((score, row))
            raw_scored.sort(key=lambda pair: pair[0], reverse=True)

            mem_scored = []
            for memory in memories:
                content = rhee.row_content(memory)
                low = content.lower()
                if not any(token in low for token in tokens):
                    continue
                score = rhee.calculate_memory_score(memory, alias_query)
                if score > 0:
                    mem_scored.append((score, memory))
            mem_scored.sort(key=lambda pair: pair[0], reverse=True)

            for score, row in raw_scored[:RAW_PER_ALIAS]:
                row_id = row.get("id")
                source = f"raw_catchall:{row_id}" if row_id is not None else ""
                content = rhee.safe_text(row.get("content"))
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1500]
                if used + len(excerpt) > CHAR_BUDGET:
                    break
                item = {"source": source, "quote_source": excerpt, "role": rhee.safe_text(row.get("role", "unknown")).lower(), "created_at": rhee.safe_text(row.get("created_at")), "deep_recall_alias": f"{left} <-> {right}", "deep_recall_alias_score": score}
                evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt)

            for score, memory in mem_scored[:MEMORY_PER_ALIAS]:
                table = rhee.safe_text(memory.get("_table", "memory"))
                memory_id = memory.get("id")
                source = f"{table}:{memory_id}" if memory_id is not None else ""
                content = rhee.row_content(memory)
                if not source or source in seen or not content:
                    continue
                excerpt = content[:1500]
                if used + len(excerpt) > CHAR_BUDGET:
                    break
                item = {"source": source, "quote_source": excerpt, "role": rhee.memory_source_role(memory), "created_at": rhee.safe_text(memory.get("created_at")), "raw_id": memory.get("raw_id"), "deep_recall_alias": f"{left} <-> {right}", "deep_recall_alias_score": score}
                evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL EVIDENCE-DISCOVERED ALIAS BRIDGE",
                "These records were found by following alias/name links explicitly discovered in retrieved evidence.",
                "Treat the alias as a retrieval lead only; the source evidence must support any identity/relationship claim in the answer.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | ALIAS={item.get('deep_recall_alias')} | ROLE={rhee.safe_text(item.get('role')).upper()}")
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_alias_bridge": "applied",
            "deep_recall_alias_links_followed": followed,
            "deep_recall_alias_added": len(additions),
            "deep_recall_alias_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
