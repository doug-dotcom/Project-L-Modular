"""Layer 15 — relevance-centred deep-recall excerpts.

Deep recall can find the right long record but ordinary excerpts often show only
the beginning. For explicit deep recall, reopen selected source records and add
continuous windows centred on the user's actual/expanded query terms. This
preserves source truth while exposing details buried later in long records.
"""
import re

WINDOW = 1800
MAX_WINDOWS = 40


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def best_window(content, query):
        text = rhee.safe_text(content)
        if len(text) <= WINDOW:
            return text, 0
        terms = []
        for term in list(rhee.query_words(query)) + list(rhee.expanded_query_terms(query)):
            term = rhee.safe_text(term).lower().strip()
            if len(term) >= 3 and term not in terms and term != "deep recall":
                terms.append(term)
        lowered = text.lower()
        hits = []
        for term in terms:
            match = re.search(r"\b" + re.escape(term) + r"\b", lowered)
            if match:
                hits.append(match.start())
        if not hits:
            return text[:WINDOW], 0
        centre = min(hits)
        start = max(0, centre - WINDOW // 3)
        start = min(start, max(0, len(text) - WINDOW))
        return text[start:start + WINDOW], start

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        raw_index = {
            f"raw_catchall:{row.get('id')}": row
            for row in rhee.load_all_raw_catchall() if row.get("id") is not None
        }
        memory_index = {
            f"{rhee.safe_text(row.get('_table'))}:{row.get('id')}": row
            for row in rhee.load_all_memories()
            if row.get("_table") and row.get("id") is not None
        }

        windows = []
        seen = set()
        for item in list(result.get("evidence") or []):
            if len(windows) >= MAX_WINDOWS:
                break
            source = rhee.safe_text(item.get("source"))
            if not source or source in seen:
                continue
            row = raw_index.get(source) or memory_index.get(source)
            if not row:
                continue
            content = (rhee.safe_text(row.get("content")) if source.startswith("raw_catchall:")
                       else rhee.row_content(row))
            if not content:
                continue
            excerpt, offset = best_window(content, query)
            # Only add a new window when it reveals text beyond the ordinary
            # leading excerpt or when the source itself is short.
            windows.append((source, excerpt, offset, rhee.safe_text(item.get("role"))))
            seen.add(source)

        output = dict(result)
        context = rhee.safe_text(output.get("context"))
        if windows:
            lines = [
                "DEEP RECALL MATCH-CENTRED SOURCE WINDOWS",
                "These are continuous extracts from already-selected sources, centred on query-relevant text.",
                "They do not create new facts and retain the source/provenance rules above.",
                "",
            ]
            for source, excerpt, offset, role in windows:
                lines.append(f"SOURCE {source} | ROLE={role.upper()} | OFFSET={offset}")
                lines.append(excerpt)
                lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({
            "deep_recall_match_windows": len(windows),
            "deep_recall_match_window_chars": WINDOW,
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet
