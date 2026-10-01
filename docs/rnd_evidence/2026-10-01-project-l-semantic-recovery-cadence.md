# Project L R&D Evidence — Semantic Recovery Cadence

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Project L semantic cron recovery cadence
- **Tags:** R&D, AI, memory, semantics, PostgreSQL, Supabase, cron, backpressure, reliability, commercialisation

## Objective / problem

Project L production releases remained blocked by sustained shared-database pressure. The trace-trust gate correctly exhausted its bounded snapshot-recovery window because PostgREST could not obtain schema-cache/database access for longer than seven seconds.

PostgreSQL logs showed widespread cron startup timeouts. Project L itself contributed two background semantic jobs:
- job 117: `private.project_l_semantic_cron_tick_v1()`;
- job 119: `private.project_l_semantic_circuit_breaker_v1()`.

Both were observed starting in the same saturated windows and both experienced startup timeouts.

## Technical uncertainty

It was uncertain whether Project L could reduce its contribution to shared database pressure without changing live owner-scoped recall, memory correctness, semantic worker batch limits, or unrelated Shine applications.

## Hypothesis / intended approach

Live Rhee / memory recall currently uses the owner-scoped v2 retrieval path and does not require these semantic maintenance jobs to run every five minutes.

Reduce only Project L's two background semantic cadences:
- semantic tick: every 15 minutes at minutes 7,22,37,52;
- semantic circuit breaker: every 15 minutes at minutes 12,27,42,57.

Leave the already-staggered semantic activation preflight unchanged. Do not modify Fiona, Rivers or Shine Me schedules.

## Production evidence

During the sustained failure window:
- PostgREST repeatedly returned `PGRST002 Could not query the database for the schema cache`;
- PostgreSQL reported large clusters of `cron job ... job startup timeout`;
- job 117 and job 119 both timed out during the same storms;
- direct Supabase SQL from the agent also timed out;
- the trace-trust predeploy smoke correctly failed closed after its 2s/5s snapshot-recovery window;
- the semantic worker completion-write backpressure fix (#256) was already live as Edge Function version 7.

## Change / experiment

Migration:
`supabase/migrations/20261001044500_project_l_semantic_recovery_cadence.sql`

Changes:
- retunes only `project_l_semantic_cron_tick_v1()` from `*/5` to `7-59/15`;
- retunes only `project_l_semantic_circuit_breaker_v1()` from `*/5` to `12-59/15`;
- uses `cron.alter_job()`;
- requires the expected old schedule before changing a job;
- does not touch activation preflight, Fiona, Rivers or Shine Me.

## Tests / evidence

- Branch: `project-l/semantic-recovery-cadence-20261001`
- CI result: pending at contemporaneous capture.
- Live database application is not claimed until Supabase accepts and verifies the migration.

## Failures / unexpected behaviour

No implementation failure had been observed at capture time. The database itself was still intermittently unavailable, so live application must be proven separately.

## Learning

When a shared database is saturated, background semantic maintenance should yield before user-facing recall or trust verification is made more tolerant. Cadence reduction is a lower-risk backpressure control than increasing live recall or trust timeouts.

## Next step

Run the full Project L suite, merge only on green, apply the exact migration when the database control plane accepts writes, verify the live cron schedules, and then redeploy the Rhee profiler.

## Source artefacts

- `supabase/migrations/20261001044500_project_l_semantic_recovery_cadence.sql`
- `tests/test_semantic_recovery_cadence.py`
- PostgreSQL / PostgREST production logs
- failed Railway deployment `b43e01c0-888a-4742-8584-30e6fda30d67`

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
