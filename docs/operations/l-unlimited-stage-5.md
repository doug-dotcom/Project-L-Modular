# Stage 5 — Retrieve at the right depth

6 September 2026. Controlled retrieval pilot, not a claim of complete recall or a
general benchmark improvement. Stage 4 remains the authority for registered,
operator-curated effective-time facts.

## Behaviour

- Focused questions: 40 raw / 24 long-term indexed candidates, six selected from
  each. Investigative questions retain larger bounded candidate pools.
- Period reviews: one fresh backend RPC over raw records and dated episodes,
  with 24 candidates and up to six supplied sources per calendar-month bucket.
  A rolling six-month window may touch seven calendar months, with partial edges.
- Explicit `from YYYY-MM-DD to YYYY-MM-DD` / `between ... and ...` periods and
  last/past one to twelve months are supported. A Pauline report without dates
  explicitly defaults to six months. Invalid or oversized periods fail closed.
- Month-level source-linked extracts support the generated synthesis. The server
  appends a coverage note independently of the model. Empty means no usable
  evidence was supplied, not that nothing happened.
- Raw timestamps are labelled recording dates; episode metadata is labelled
  event date. A recent retelling is not evidence that an old event happened again.
- No model extraction, durable summary cache, asynchronous refresh, new memory
  copies, raw deletion or new background jobs. Original raw rows are retained,
  with `raw_id` links beneath episode summaries. Existing generated FTS indexes
  update in the source transaction; each period request queries afresh.

## Budgets and limits

The period RPC has an eight-second database timeout, at most a 366-day window,
24 search terms, and 48 candidates per month maximum (caller uses 24). Transport
content is at most 6,000 characters per row, explicitly marked when clipped.
Model excerpts are continuous slices of at most 1,200 characters, with offsets;
the period evidence budget is 60,000 characters. The selected six per month
actually bound period extracts to at most 93,600 characters before that budget.
Candidate and selection limits appear in the receipt and coverage note.

Focused legacy retrieval has a six-second elapsed acceptance budget; investigation
and period retrieval have twelve seconds. These are measured acceptance budgets,
not promises to cancel a blocking network call at the deadline. The existing
client/network timeout still applies. Over-budget or unavailable retrieval is
not sent for generation. No full-corpus database fallback is allowed through the
live context entry point. Existing offline diagnostic helpers remain available.
The temporal-fact check, broader cognitive pipeline and model generation have
their own budgets; this is not a whole-request latency guarantee.

General report wording outside the supported period grammar may take the
investigative path. This pilot does not infer all natural-language date ranges.
Period retrieval covers `raw_catchall` recording dates and ISO-date
`episodic_memories` event dates, not every date embedded in every legacy blob.
It does not automatically migrate old imports into correctly dated episodes.
Legacy short-term context and unlinked domain summaries are deliberately not
injected into the period evidence packet as substitutes for missing months.
The broader cognitive pipeline may still supply background; its background is
not month-specific evidence and cannot bypass the existing citation contract.

## Security and verification

`l_recall_period` is SECURITY INVOKER, empty search path, service-role execution
only; anon/authenticated/PUBLIC execution revoked. It reads the existing
single-owner L corpus. It is not a multi-user API or an expansion of browser
recovery-token authority. No new tables or RLS policies are introduced.

- `tests/test_recall_planner.py`: date edges, gaps, per-month allocation,
  provenance, bounds, unavailable/malformed results, no-cache visibility,
  Rhee wiring and fail-closed server behaviour.
- `supabase/tests/recall_period.sql`: transactional synthetic insert/search,
  six-month gaps, source preservation, historical retelling, Brisbane midnight,
  role grants and period bounds. Fixtures roll back.
- `scripts/check_l_recall_models.py`: two synthetic-only configured-model calls,
  real citation evaluation, required six-month labels and honest gap blocks.
  Never reads private memory. Run explicitly once, not as a recurring job.
- Existing Stage 4 tests continue to measure curated current-fact correctness.

Receipts retain retrieval latency, candidate/source counts, month evidence
coverage and limits. Existing model receipts retain actual token usage, timing
and model identity. Synthetic source-ID coverage is testable; semantic relevance
and real-world evidence completeness are not independently certified. The SQL
visibility check measures same-transaction searchability, not a production
cross-transaction ingestion-lag SLA.

Implementation references: [Supabase timeouts](https://supabase.com/docs/guides/database/postgres/timeouts)
and [database functions](https://supabase.com/docs/guides/database/functions).

## Rollback

Revert the Stage 5 application commit through a reviewed GitHub change. The
read-only RPC/index can remain unused; do not drop source data. Removing the
pilot re-enables the previous retrieval behaviour and its limitations. Never
leave the synthetic provider test configured as a recurring deployment command.
