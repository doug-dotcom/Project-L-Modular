"""Layer 32 — Deep Recall primary-source provenance backfill.

Deep Recall may retrieve a promoted/canonical memory whose raw_id points back to
Doug's original raw record. Layer 27 can recognise that lineage, but recognition
alone does not guarantee the primary source itself is present in the evidence
packet. This layer follows retrieved raw_id provenance back to raw_catchall and
adds the matching source record when available.

It never assumes the derived memory is wrong, never invents missing provenance,
and never treats an unavailable raw ancestor as evidence that none existed.
Ordinary Recall is unchanged.
"""

MAX_BACKFILLS = 24
CHAR_BUDGET = 36000


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

        wanted = []
        seen_ids = set()
        for item in evidence:
            raw_id = item.get("raw_id")
            if raw_id is None:
                continue
            rid = rhee.safe_text(raw_id).strip()
            if not rid or rid in seen_ids or f"raw_catchall:{rid}" in seen_sources:
                continue
            wanted.append(rid)
            seen_ids.add(rid)
            if len(wanted) >= MAX_BACKFILLS:
                break

        if not wanted:
            output = dict(result)
            plan = dict(output.get("recall_plan") or {})
            plan.update({
                "deep_recall_provenance_backfill": "not_needed",
                "deep_recall_provenance_requested": 0,
                "deep_recall_provenance_added": 0,
            })
            output["recall_plan"] = plan
            return output

        raw_index = {}
        for row in rhee.load_all_raw_catchall():
            rid = rhee.safe_text(row.get("id")).strip()
            if rid in seen_ids:
                raw_index[rid] = row

        additions = []
        used = 0
        for rid in wanted:
            row = raw_index.get(rid)
            if not row:
                continue
            content = rhee.safe_text(row.get("content"))
            if not content:
                continue
            excerpt = content[:1800]
            if used + len(excerpt) > CHAR_BUDGET:
                break
            source = f"raw_catchall:{rid}"
            item = {
                "source": source,
                "quote_source": excerpt,
                "role": rhee.safe_text(row.get("role", "unknown")).lower(),
                "created_at": rhee.safe_text(row.get("created_at")),
                "deep_recall_provenance_backfill": True,
            }
            evidence.append(item)
            additions.append(item)
            seen_sources.add(source)
            used += len(excerpt)

        output = dict(result)
        output["evidence"] = evidence
        context = rhee.safe_text(output.get("context"))
        if additions:
            lines = [
                "DEEP RECALL PRIMARY-SOURCE PROVENANCE BACKFILL",
                "These raw records were added because retrieved derived/promoted memories explicitly pointed to them by raw_id.",
                "Prefer Doug-authored raw evidence for the underlying autobiographical claim under the existing authority rules.",
                "A raw ancestor and its derived memory are one lineage, not independent corroboration.",
                "",
            ]
            for item in additions:
                lines.append(
                    f"SOURCE {item['source']} | ROLE={rhee.safe_text(item.get('role')).upper()} | "
                    f"CREATED_AT={item.get('created_at', '')}"
                )
                lines.append(rhee.safe_text(item.get("quote_source")))
                lines.append("")
            context += "\n\n" + "\n".join(lines)

        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(evidence) or bool(result.get("recall_active"))
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_provenance_backfill": "applied",
            "deep_recall_provenance_requested": len(wanted),
            "deep_recall_provenance_added": len(additions),
            "deep_recall_provenance_missing": len(wanted) - len(additions),
            "deep_recall_provenance_chars": used,
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet

    from layers.layer33_deep_recall_time_window_rescue import install as install_time_window_rescue
    install_time_window_rescue(rhee)
