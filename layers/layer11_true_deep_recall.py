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

    def search(query, raw_limit=200, memory_limit=80):
        if not explicit_deep_recall(query):
            return previous_search(query, raw_limit=raw_limit, memory_limit=memory_limit)

        started = rhee.time.monotonic()
        # These loaders paginate every live Supabase memory table plus
        # raw_catchall. load_all_memories also includes the shipped historical
        # domain corpus and applies provenance annotation/deduplication.
        raw_rows = [dict(row) for row in rhee.load_all_raw_catchall()]
        memory_rows = [dict(row) for row in rhee.load_all_memories()]
        elapsed = round((rhee.time.monotonic() - started) * 1000)
        print("=" * 60)
        print("TRUE DEEP RECALL FULL-CORPUS SCAN")
        print(f"RAW ROWS INSPECTABLE     : {len(raw_rows)}")
        print(f"MEMORY ROWS INSPECTABLE  : {len(memory_rows)}")
        print(f"FULL SCAN LOAD MS        : {elapsed}")
        print("=" * 60)
        return {"raw": raw_rows, "memories": memory_rows}

    rhee.plan_recall = plan
    rhee.search_database_candidates = search
