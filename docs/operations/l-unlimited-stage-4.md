# Stage 4 — Time-aware facts and correction propagation

This extends the newer Unlimited roadmap, not Phase 4 (Mary) of the older programme.

## Scope and authority

Operator-curated records contain subject/property, claim, effective start/end dates,
observation time, recording time, original source reference/passage, source authorship
and replacement links. Validity is day-granular with an exclusive end date. Unknown
effective dates are not guessed. Future events are not asserted as accomplished facts.

The existing private service connection owns the RPCs. All four new tables have RLS,
no anon/authenticated grants, and owner-scoped compound foreign keys. RPCs use invoker
security and a fixed empty search path. `L_MEMORY_OWNER_ID` configures the personal
memory namespace (default: deterministic UUID for this single-owner L deployment).
It is NOT an Auth identity and NOT the browser recovery-token owner. This does not
claim to implement multi-user authentication for the existing legacy memory tables.

Model output and ordinary chat cannot write, correct or delete these facts. An
authorised operator uses `python -m scripts.manage_l_facts write` with RPC parameters
as JSON on stdin. Include a stable `p_id` UUID for idempotency; subject, predicate,
claim, explicit date interval, observation time, source reference, exact source passage,
source role and action. `p_claim` must occur inside the supplied passage. The operator
must verify the original source and interpretation: substring validation is NOT
independent semantic verification. Do not put personal inputs in shell history.

## Distinct operations

- `assert`: a non-overlapping dated fact; conflicts require explicit resolution.
- `transition`: close a prior interval and start its replacement. Earlier history stays valid.
- `correct`: mark the mistaken fact corrected and insert its replacement. Original evidence stays in the journal.
- `observe`: record another mention of an existing fact. It cannot change effective dates or current status.
- `request-removal`: produce a pending inventory for a separately authorised removal workflow. It does not erase anything.

Writes lock the individual owner/subject/property group. Its derived timeline summary
is rebuilt in the same transaction and revision incremented. The timeline index and
subsequent Rhee snapshot see the correction together. Unrelated groups are unchanged.

## Recall and saved answers

Rhee reads a fresh atomic snapshot, not a process cache. Current questions select
valid intervals for Brisbane's date; explicit ISO dates and named months select
historical intervals. A month without a year uses its latest occurrence and exposes
that assumption. Other historical phrasing yields the dated timeline, not a silent
current-date guess. Gaps stay unknown; mid-month changes return all matching intervals.

Selected curated facts join the ordinary evidence contract with actual source roles
and explicit operator-curated authority. Prior assistant messages cannot grant
themselves that authority. Matching legacy evidence is still supplied for context,
but the dated curated claim is designated authoritative for that subject/property.
This is not a semantic guarantee that a model will always obey that distinction.

Answers carry query terms, group revisions and the selected time window. Before
publishing, the server checks freshness. A correction made during generation causes
the answer to be withheld, not saved as a fresh assistant answer. On later recovery,
the original result and receipt remain immutable; a separate freshness annotation
warns if matching groups changed or appeared. The UI displays that warning both in
normal recovery and Saved answers. No automatic model replay or paid regeneration.

## Boundaries and removal policy

This is a curated fact layer, NOT an automatic conversion of millions of legacy
words. Old summaries, embeddings, raw memories, working-memory text and user-pasted
copies without dependency links are not retroactively rewritten. Only registered
fact timelines and tracked answers have mechanical correction propagation. Curating
historical facts requires source review, not wholesale inference or date guessing.

Deletion requires reviewing the original source, legacy derivatives, registered fact
and observation copies, timelines/indexes, durable answers, browser copies and backup
retention. A pending request is not a deletion receipt. No erasure is implemented or
performed by this stage; a separate authorised removal procedure must close the inventory.

## Verification and rollback

`supabase/tests/temporal_facts.sql` runs synthetic acceptance cases inside a rollback
transaction: June versus current, recent mention, correction, summary refresh,
unrelated-fact preservation, negative-cache invalidation, owner isolation, conflict
rejection, idempotency and deletion-request non-erasure. It leaves no personal or
synthetic fact rows behind. Python regressions exercise Rhee, dates, source authority,
freshness failures and saved-payload immutability.

Apply `supabase/create_temporal_facts.sql` as one recorded backend migration before
deploying the application. Rollback application code if needed; retain the additive
tables/history, never delete personal facts to roll back code.

Security references reviewed: [Supabase functions](https://supabase.com/docs/guides/database/functions)
and [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).
