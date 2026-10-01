# Project L R&D Evidence — Semantic Background Yield

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Semantic background yield / live-recall contention reduction
- **Tags:** R&D, AI, memory, reliability, PostgreSQL, Supabase, observability, deployment-safety, commercialisation

## Objective / problem

Restore reliable owner-scoped live recall after production predeploy memory canaries repeatedly failed with PostgreSQL `57014 statement timeout`.

The deployment smoke was already hardened to honour one bounded transient replay, but the replay also timed out. This demonstrated a real database contention problem rather than a smoke-test false positive.

## Technical uncertainty

It was uncertain whether the recall function itself was intrinsically too slow, or whether shared/background database work was consuming enough resources to make a normally-fast recall function miss its strict five-second database statement timeout.

Increasing recall timeouts was deliberately rejected as the first response because it could hide saturation and increase queueing.

## Production evidence

During the failure window:
- `project_l_memory_context_service_v2` returned PostgreSQL `57014 canceling statement due to statement timeout`;
- a separate Shine Me RPC also timed out, showing the issue was broader than one memory function;
- Project L semantic cron job 117 ran for approximately **95.07 seconds**;
- semantic activation preflight job 118 ran for approximately **121.07 seconds** before statement-timeout failure;
- multiple minute cron jobs reported startup timeout;
- a shared database audit scan and other large-table work were also active during the same contention window;
- the memory bridge's bounded replay correctly failed closed after the second real timeout.

## Hypothesis

Live recall can remain strict and fast if non-user-facing semantic background work:
1. bounds resource-limit history to recent semantic dispatches before joining pg_net response history; and
2. avoids starting the 15-minute activation preflight at the same instant as the five-minute semantic worker.

## Change / experiment

Migration:
`supabase/migrations/20261001024000_project_l_semantic_background_yield.sql`

Changes:
- replaces `private.project_l_semantic_recent_resource_limit_v1()`;
- reads the cooldown policy into a scalar first;
- uses the existing `l_semantic_worker_dispatches_created_idx`;
- materializes at most 64 recent request IDs before the pg_net join;
- preserves HTTP 546 resource-limit cooldown semantics;
- leaves live memory statement/client timeouts unchanged;
- moves semantic activation preflight from `*/15 * * * *` to `2-59/15 * * * *`;
- does not retune Fiona, Rivers or other estate workloads.

## Tests / evidence

- Original source PR: #250 — **Make semantic background work yield to live recall**
- Original CI run: `36807009761`
- Original regression result: **PASS — 1,722 passed, 5 warnings, 13 subtests passed in 29.29s**
- New contract tests: `tests/test_semantic_background_yield.py`
- Live migration applied successfully to Project L Supabase.
- Live activation-preflight schedule verified as `2-59/15 * * * *`.
- Old planner estimate for the resource-limit probe was approximately **12,156 total cost**, with sequential scans of semantic dispatch history and pg_net response history.
- Rewritten inner query uses `l_semantic_worker_dispatches_created_idx`, materialized **5 current recent dispatches** at measurement time, and completed in approximately **3.28 ms**.
- A subsequent helper timing completed in approximately **1.53 ms** under recovered load.
- After the migration, job 118 completed four consecutive scheduled runs successfully in approximately **4.18s, 5.09s, 4.55s and 4.40s**.
- The pre-migration failure immediately before those runs was **121.07s** with statement-timeout failure.
- Replacement PR #253 rebased the change onto current Project L main after the indexed-claim-hash and current-process readiness layers.
- Current-main regression result: **PASS — 1,729 passed, 5 warnings, 13 subtests passed in 33.11s**.
- PR #253 merged as commit `d2629628ec7ca210937bead875698839c6a096fd`.

## Failures / unexpected behaviour

The first post-migration helper timing was approximately 4.49 seconds while residual shared database pressure remained. Isolating the inner query immediately afterwards showed the rewritten plan itself was low-millisecond. This distinguishes workload pressure from query-plan cost and avoids falsely claiming the migration alone eliminates all shared-database saturation.

## Learning

The failure was not fixed by making live recall more patient. The better architecture is for background semantic work to yield:
- keep live recall bounded and fail-closed;
- reduce accidental synchronized cron pressure;
- bound historical background probes before joining shared extension tables;
- treat shared database contention as an operational condition rather than silently extending user-facing latency.

## Next step

Retain live recall's strict statement/client timeouts, continue observing scheduled semantic jobs under normal load, and preserve the separation between current process health and durable recovery evidence.

## Source artefacts

- Original PR #250 (superseded and closed)
- Rebased merged PR #253
- `supabase/migrations/20261001024000_project_l_semantic_background_yield.sql`
- `tests/test_semantic_background_yield.py`
- `.github/workflows/ci.yml`
- Supabase Project L cron/job-run evidence
- Project L memory bridge/Railway deployment logs

## Time / cost

Engineering time is represented by contemporaneous GitHub, Supabase and Railway timestamps. No external monetary cost is claimed.
