# Project L R&D Evidence — Durable Lease Reaper Yield

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Durable-task lease reaper load shedding
- **Tags:** R&D, AI, reliability, PostgreSQL, Supabase, backpressure, durable-tasks, deployment-safety, commercialisation

## Objective / problem

Project L production releases were repeatedly blocked by shared Supabase/PostgREST connection pressure. During the outage window, PostgREST repeatedly returned `PGRST002 Could not query the database for the schema cache`, the Supabase SQL control plane could not execute even `select 1`, and Railway predeploy could not reach the Rhee profiler.

Production PostgREST logs showed repeated `/rpc/l_task_reap_expired` calls from Project L's Python runtime during the same schema-cache outage.

## Technical uncertainty

It was uncertain whether Project L's durable-task dispatcher was amplifying database pressure by running global lease-expiry maintenance too frequently, and whether that maintenance could yield without changing:
- durable claim safety;
- one-shot claim tokens;
- lease/heartbeat semantics;
- terminal persistence;
- no-replay connected-action guarantees;
- or normal queue pickup behaviour.

## Production evidence

The dispatcher has two worker slots. Before this experiment, every slot called `l_task_reap_expired(limit=100)` before every queue poll, while idle polls occur approximately every 3 seconds.

That architecture can issue up to roughly **40 lease-reaper maintenance RPCs per minute per process** even when there is no expired work.

During the outage window:
- PostgREST connection pool repeatedly reinitialised with **maximum size 10**;
- `PGRST002` schema-cache failures were widespread;
- `l_task_reap_expired` appeared repeatedly in the failing request stream;
- the trace-trust snapshot and unrelated Me activation RPCs also returned HTTP 503;
- the Supabase SQL control plane reported `Connection terminated due to connection timeout`.

Supabase documentation identifies this timeout pattern as database overload/outage behaviour and recommends reducing strain / optimizing load before merely increasing timeouts.

## Hypothesis / intended approach

Lease reaping is maintenance, not a prerequisite for claiming queued work.

Use one process-wide maintenance cadence:
- healthy reaper interval: **30 seconds**;
- reaper failure backoff: **60 seconds**;
- only one worker slot may own a maintenance attempt at a time;
- reserve the next maintenance window before touching the database so sibling slots cannot stampede a blocked RPC;
- a maintenance failure does **not** block the independent queue claim attempt.

Claims, heartbeats, one-shot tokens and terminal persistence remain unchanged.

## Change / experiment

Modified `core/cognition/durable_tasks.py`:
- added a process-wide non-blocking reaper lock;
- added `_next_reap_at` cadence state;
- added configurable 30-second healthy interval;
- added configurable 60-second failure backoff;
- moved reaper errors out of the main dispatcher failure path;
- kept claim behaviour independent.

Added `tests/test_durable_reaper_yield.py` proving:
1. repeated maintenance calls are suppressed inside the cadence;
2. a failed reaper receives the longer backoff;
3. reaper failure does not block a queue claim.

## Expected load effect

At two idle worker slots:
- before: potentially ~40 maintenance reaper RPCs/minute;
- after: at most ~2 successful maintenance attempts/minute per process;
- after a maintenance failure: at most ~1 attempt/minute until recovery.

This changes maintenance load only; it does not reduce claim polling or alter durable-task correctness.

## Tests / evidence

- Branch: `project-l/durable-reaper-yield-20261001`
- CI result: pending at contemporaneous capture.
- Live deployment and PostgREST request behaviour must be appended from actual evidence.

## Failures / unexpected behaviour

The live semantic cadence migration intended to reduce cron pressure could not be applied because Supabase's SQL/migration channels themselves were timing out. This experiment therefore targets a Project L load source that can be changed through the application runtime without requiring a database migration.

## Learning

Maintenance loops must be pressure-aware. A correct bounded mutation can still become harmful when it is invoked by every worker on every idle poll. Process-wide coordination is a lower-risk load-shedding mechanism than raising database or trust timeouts.

## Next step

Run the full current Project L regression suite, merge only on green, deploy the exact runtime commit, and compare production PostgREST/reaper behaviour before retrying the Rhee profiler.

## Source artefacts

- `core/cognition/durable_tasks.py`
- `tests/test_durable_reaper_yield.py`
- `.github/workflows/ci.yml`
- Supabase PostgREST/PostgreSQL outage logs
- Supabase troubleshooting documentation for database connection timeouts / PGRST002

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
