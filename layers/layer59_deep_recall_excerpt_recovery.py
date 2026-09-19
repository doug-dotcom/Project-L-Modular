"""Layer 59 — Deep Recall clipped-excerpt recovery.

Layer 58 detects evidence windows that appear to be cut at a character boundary.
Detection alone prevents guessing, but Deep Recall can often do better: the full
source is already available in the corpus. This layer reopens flagged sources and
adds a bounded continuation/context window around the clipped edge.

Recovered text is explicitly the SAME source and cannot count as independent
corroboration. Stored memories are never modified. Ordinary Recall is unchanged.
"""
import re

MAX_RECOVERIES = 24
RECOVERY_CHARS = 2600
CHAR_BUDGET = 48000

TRAILING_COMPLETE_RE = re.compile(r'(?:[.!?][\"”’\')\]]?)\s*$')
LEADING_FRAGMENT_RE = re.compile(r'^[a-z0-9,;:)\]]')


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def trailing_clip(text):
        clean = rhee.safe_text(text).rstrip()
        if len(clean) < 250:
            return False
        if clean.endswith(("…", "...")):
            return True
        return not bool(TRAILING_COMPLETE_RE.search(clean))

    def leading_clip(text):
        clean = rhee.safe_text(text).lstrip()
        return bool(clean) and bool(LEADING_FRAGMENT_RE.search(clean[:1]))

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        candidates = []
        for item in evidence:
            excerpt = rhee.safe_text(item.get("quote_source"))
            if trailing_clip(excerpt) or leading_clip(excerpt):
                source = rhee.safe_text(item.get("source")).strip()
                if source:
                    candidates.append((source, excerpt))

        if not candidates:
            output = dict(result)
            plan = dict(output.get("recall_plan") or {})
            plan.update({
                "deep_recall_excerpt_recovery": "not_needed",
                "deep_recall_excerpt_recovery_count": 0,
            })
            output["recall_plan"] = plan
            return output

        wanted = {source for source, _ in candidates[:MAX_RECOVERIES]}
        full_sources = {}

        for row in rhee.load_all_raw_catchall():
            source = f"raw_catchall:{row.get('id')}" if row.get("id") is not None else ""
            if source in wanted:
                full_sources[source] = rhee.safe_text(row.get("content"))

        for memory in rhee.load_all_memories():
            table = rhee.safe_text(memory.get("_table", "memory"))
            source = f"{table}:{memory.get('id')}" if memory.get("id") is not None else ""
            if source in wanted:
                full_sources[source] = rhee.row_content(memory)

        recoveries = []
        used = 0
        seen = set()

        for source, excerpt in candidates:
            if source in seen or len(recoveries) >= MAX_RECOVERIES:
                continue
            full = full_sources.get(source, "")
            if not full or len(full) <= len(excerpt):
                continue

            # Locate a stable piece of the excerpt in the full source. Prefer the
            # tail for trailing clips, otherwise the head.
            clean = excerpt.strip()
            anchors = []
            if trailing_clip(excerpt):
                anchors.extend([clean[-240:], clean[-120:], clean[-60:]])
            if leading_clip(excerpt):
                anchors.extend([clean[:240], clean[:120], clean[:60]])
            anchors.extend([clean[:160], clean[-160:]])

            pos = -1
            anchor_used = ""
            for anchor in anchors:
                if not anchor:
                    continue
                pos = full.find(anchor)
                if pos >= 0:
                    anchor_used = anchor
                    break
            if pos < 0:
                continue

            if trailing_clip(excerpt):
                start = max(0, pos - 500)
                end = min(len(full), pos + len(anchor_used) + RECOVERY_CHARS)
            else:
                start = max(0, pos - RECOVERY_CHARS // 2)
                end = min(len(full), start + RECOVERY_CHARS)

            window = full[start:end].strip()
            if not window or window == clean:
                continue
            if used + len(window) > CHAR_BUDGET:
                break

            recoveries.append((source, window))
            seen.add(source)
            used += len(window)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_excerpt_recovery": "applied" if recoveries else "unresolved",
            "deep_recall_excerpt_recovery_candidates": len(candidates),
            "deep_recall_excerpt_recovery_count": len(recoveries),
            "deep_recall_excerpt_recovery_chars": used,
            "deep_recall_excerpt_recovery_sources": [s for s, _ in recoveries],
        })
        output["recall_plan"] = plan

        if recoveries:
            lines = [
                "DEEP RECALL CLIPPED-EXCERPT RECOVERY",
                "The following windows reopen sources whose earlier evidence excerpt appeared clipped at a boundary.",
                "Each recovery is from the SAME source as the clipped excerpt; it is additional context, not independent corroboration.",
                "Use the recovered window to resolve a cut-off proposition only where the text itself completes it. Never infer missing words beyond the recovered source.",
                "",
            ]
            for source, window in recoveries:
                lines.append(f"SOURCE {source} | RECOVERED_BOUNDARY_CONTEXT=YES")
                lines.append(window)
                lines.append("")
            context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
            output["context"] = context
            output["context_size"] = len(context)

        return output

    rhee.build_context_packet = packet

    from layers.layer60_deep_recall_event_identity_guard import install as install_event_identity_guard
    install_event_identity_guard(rhee)
