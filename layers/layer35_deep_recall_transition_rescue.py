"""Layer 35 — Deep Recall transition-event rescue.

Broad autobiographical timelines are often defined by transitions: started,
joined, left, moved, changed, ended, returned, promoted, retired and similar
events. A relevance ranking can retrieve the stable stages but miss the small
record that explains how one stage became the next.

For explicit broad/timeline Deep Recall, this layer makes a dedicated full-corpus
pass for subject-relevant transition records. Transition words are retrieval
signals only; the underlying source must support every final claim.
Ordinary Recall is unchanged.
"""
import re

MAX_ADDITIONS = 28
CHAR_BUDGET = 40000

BROAD_RE = re.compile(
    r"\b(?:complete|entire|whole|full|chronolog|timeline|history|beginning|end|"
    r"career|schooling|life before|life after|across my life|working life)\b", re.I
)
TRANSITION_RE = re.compile(
    r"\b(?:started|began|joined|entered|enlisted|left|quit|resigned|moved|relocated|"
    r"returned|changed|transitioned|transferred|promoted|appointed|became|ended|"
    r"finished|graduated|discharged|retired|separated|married|engaged|divorced|"
    r"opened|closed|sold|bought|founded|launched|diagnosed|admitted|released|"
    r"deployed|posted|transferred|commenced|ceased)\b", re.I
)


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query) or not BROAD_RE.search(rhee.safe_text(query)):
            return result

        evidence = list(result.get("evidence") or [])
        seen = {rhee.safe_text(item.get("source")) for item in evidence}
        initial_transition_sources = sum(
            1 for item in evidence
            if TRANSITION_RE.search(rhee.safe_text(item.get("quote_source")))
        )

        raw_scored = []
        for row in rhee.load_all_raw_catchall():
            content = rhee.safe_text(row.get("content"))
            if not content or not TRANSITION_RE.search(content):
                continue
            score = rhee.calculate_raw_score(row, query)
            if score > 0:
                raw_scored.append((score, row))
        raw_scored.sort(key=lambda pair: pair[0], reverse=True)

        mem_scored = []
        for memory in rhee.load_all_memories():
            content = rhee.row_content(memory)
            if not content or not TRANSITION_RE.search(content):
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
            excerpt = content[:1700]
            if used + len(excerpt) > CHAR_BUDGET:
                break
            item = {
                "source": source, "quote_source": excerpt,
                "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_transition": True,
                "deep_recall_transition_score": score,
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
            excerpt = content[:1700]
            if used + len(excerpt) > CHAR_BUDGET:
                break
            item = {
                "source": source, "quote_source": excerpt,
                "role": rhee.memory_source_role(memory),
                "created_at": rhee.safe_text(memory.get("created_at")),
                "raw_id": memory.get("raw_id"),
                "deep_recall_transition": True,
                "deep_recall_transition_score": score,
            }
            evidence.append(item); additions.append(item); seen.add(source); used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL TRANSITION-EVENT RESCUE",
                "These records were recovered because broad timelines need evidence about transitions between stages, not only evidence about the stages themselves.",
                "Transition vocabulary is a retrieval signal only. State a transition/date/order only when the source evidence supports it.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | TRANSITION_RESCUE=YES | ROLE={rhee.safe_text(item.get('role')).upper()}")
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)

        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_transition_rescue": "applied",
            "deep_recall_transition_initial_sources": initial_transition_sources,
            "deep_recall_transition_added": len(additions),
            "deep_recall_transition_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
