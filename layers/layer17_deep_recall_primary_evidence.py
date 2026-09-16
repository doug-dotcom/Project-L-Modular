"""Layer 17 — primary-evidence reserve for explicit deep recall.

Deep recall should not let secondary assistant summaries crowd Doug's own words
out of the expanded evidence packet. After all earlier retrieval/diversity
passes, inspect the full raw corpus for relevant USER-authored records and add a
bounded reserve of distinct primary evidence. No facts are created or promoted.
"""

PRIMARY_LIMIT = 24
PRIMARY_CHAR_BUDGET = 30000


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        seen_sources = {rhee.safe_text(item.get("source")) for item in evidence}
        scored = []
        for row in rhee.load_all_raw_catchall():
            if rhee.safe_text(row.get("role")).lower() != "user":
                continue
            score = rhee.calculate_raw_score(row, query)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        additions = []
        used = 0
        for score, row in scored:
            if len(additions) >= PRIMARY_LIMIT or used >= PRIMARY_CHAR_BUDGET:
                break
            row_id = row.get("id")
            source = f"raw_catchall:{row_id}" if row_id is not None else ""
            content = rhee.safe_text(row.get("content"))
            if not source or source in seen_sources or not content:
                continue
            excerpt = content[:1400]
            if used + len(excerpt) > PRIMARY_CHAR_BUDGET:
                break
            item = {
                "source": source,
                "quote_source": excerpt,
                "role": "user",
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_primary_score": score,
            }
            evidence.append(item)
            additions.append(item)
            seen_sources.add(source)
            used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(result.get("context"))
        if additions:
            lines = [
                "DEEP RECALL PRIMARY-EVIDENCE RESERVE",
                "These are relevant Doug-authored records from the full corpus.",
                "Treat them as primary evidence under the existing provenance rules.",
                "Do not infer missing facts or chronology from recording timestamps.",
                "",
            ]
            for item in additions:
                lines.append(f"SOURCE {item['source']} | ROLE=USER | CREATED_AT={item.get('created_at', '')}")
                lines.append(item["quote_source"])
                lines.append("")
            context += "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({
            "deep_recall_primary_reserve": "applied",
            "deep_recall_primary_sources_added": len(additions),
            "deep_recall_primary_chars_added": used,
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet

    from layers.layer18_deep_recall_completeness_ledger import install as install_completeness_ledger
    install_completeness_ledger(rhee)
