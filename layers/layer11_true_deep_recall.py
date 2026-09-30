"""Layer 11 — true deep recall contract.

Project L has two deliberately different recall commands:

* recall      = fast, indexed, bounded lookup
* deep recall = patient full-corpus inspection before ranking evidence

Doug explicitly accepts the extra latency of deep recall. Therefore an explicit
"deep recall" must not be silently reduced to the ordinary indexed candidate
window or the old 45-second target. This layer changes retrieval only: every
stored row is inspected, but only relevant evidence is injected into model
context and normal provenance/conflict rules still apply.
"""


def install(rhee):
    previous_plan = rhee.plan_recall
    previous_search = rhee.search_database_candidates

    def explicit_deep_recall(query):
        # Deep Recall is an explicit user-entry contract. Internal bounded
        # retries/rewrites may broaden wording but can never promote themselves
        # into a full-corpus scan.
        origin_guard = getattr(rhee, "_project_l_internal_recall_pass", None)
        if origin_guard is not None and bool(origin_guard.get(False)):
            return False
        text = rhee.safe_text(query).lower()
        # Internal targeted coverage passes already have their own bounded
        # search. Do not turn each sub-pass into another corpus-wide scan.
        return rhee.term_in_text("deep recall", text) and "career stage" not in text

    def plan(query, today=None):
        result = previous_plan(query, today=today)
        if not explicit_deep_recall(query):
            return result
        result = dict(result)
        result.update({
            "mode": "investigate",
            "deep_recall_contract": "full_corpus_scan",
            "full_scan_fallback": True,
            # Deep recall is intentionally patient. This is a safety ceiling,
            # not a user-facing latency promise and not a validity boundary.
            "retrieval_budget_ms": 300000,
            "contradiction_review": True,
            "coverage_review": True,
            "absence_claim_requires_full_scan": True,
        })
        return result

    def search(query, raw_limit=200, memory_limit=80, receipt_out=None):
        if not explicit_deep_recall(query):
            return previous_search(
                query,
                raw_limit=raw_limit,
                memory_limit=memory_limit,
                receipt_out=receipt_out,
            )

        started = rhee.time.monotonic()
        query_key = rhee.recall_query_key(rhee.database_search_terms(query))
        if receipt_out is not None:
            receipt_out.update(
                retrieval_query_key=query_key,
                retrieval_query_contract="full-corpus-v1",
                retrieval_query_binding="full-corpus-live-required",
            )

        if not rhee.supabase:
            if receipt_out is not None:
                receipt_out.update(
                    retrieval_status="unavailable",
                    retrieval_reason="database_not_configured",
                )
            return None

        retry_after = rhee.recall_rpc_retry_after()
        if retry_after:
            if receipt_out is not None:
                receipt_out.update(
                    retrieval_status="unavailable",
                    retrieval_reason="data_api_circuit_open",
                    retrieval_retry_after=retry_after,
                )
            return None

        try:
            # A live probe is mandatory even when process caches are warm.
            # Without it a stale cache could masquerade as a complete scan
            # during a PostgREST/schema-cache outage.
            (
                rhee.supabase
                .table("raw_catchall")
                .select("id")
                .limit(1)
                .execute()
            )

            raw_rows = []
            offset = 0
            batch_size = 1000
            while True:
                response = (
                    rhee.supabase
                    .table("raw_catchall")
                    .select("*")
                    .order("id", desc=True)
                    .range(offset, offset + batch_size - 1)
                    .execute()
                )
                batch = response.data or []
                raw_rows.extend(dict(row) for row in batch)
                if len(batch) < batch_size:
                    break
                offset += batch_size

            # Full-corpus means every live governed memory table must load.
            # Do not use load_all_memories here because its ordinary-recall
            # behaviour deliberately tolerates individual table failures.
            memory_rows = [dict(row) for row in rhee.load_local_memories()]
            for table_name in rhee.LONG_TERM_TABLES:
                table_rows = rhee.load_table_memories(table_name)
                for row in table_rows:
                    memory = dict(row)
                    memory["_table"] = table_name
                    memory_rows.append(memory)

            raw_role_index = rhee.build_raw_role_index(raw_rows)
            for memory in memory_rows:
                rhee.annotate_memory_provenance(memory, raw_role_index)
            memory_rows = rhee.deduplicate_memories(memory_rows)
        except Exception as error:
            code = rhee.recall_rpc_error_code(error)
            # Any failed component makes a claimed full-corpus scan incomplete.
            # Open the short circuit even for a non-transient failure so later
            # deep-recall enrichment layers do not cascade requests or reuse
            # stale/local-only data in this request window.
            rhee.open_recall_rpc_circuit()
            if receipt_out is not None:
                receipt_out.update(
                    retrieval_status="unavailable",
                    retrieval_reason="full_corpus_incomplete",
                    retrieval_error_code=code or "non_transient",
                    retrieval_query_binding="full-corpus-unverified",
                    retrieval_retry_after=rhee.recall_rpc_retry_after(),
                )
            print(
                "TRUE DEEP RECALL UNAVAILABLE "
                f"code={code or 'non_transient'}",
                flush=True,
            )
            return None

        rhee.close_recall_rpc_circuit()
        elapsed = round((rhee.time.monotonic() - started) * 1000)
        if receipt_out is not None:
            receipt_out.update(
                retrieval_status="checked",
                retrieval_query_binding="full-corpus-live",
                retrieval_attempts=1,
                full_scan_raw_rows=len(raw_rows),
                full_scan_memory_rows=len(memory_rows),
                full_scan_load_ms=elapsed,
            )
        print("=" * 60)
        print("TRUE DEEP RECALL FULL-CORPUS SCAN")
        print(f"RAW ROWS INSPECTABLE     : {len(raw_rows)}")
        print(f"MEMORY ROWS INSPECTABLE  : {len(memory_rows)}")
        print(f"FULL SCAN LOAD MS        : {elapsed}")
        print("=" * 60)
        return {"raw": raw_rows, "memories": memory_rows}

    rhee.plan_recall = plan
    rhee.search_database_candidates = search
