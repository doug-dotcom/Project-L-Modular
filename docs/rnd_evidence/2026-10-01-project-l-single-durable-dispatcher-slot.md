# Project L R&D Evidence — Single Production Durable Dispatcher Slot

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Production durable dispatcher concurrency reduction
- **Tags:** R&D, AI, Supabase, PostgreSQL, backpressure, durable-tasks, reliability, deployment-safety, commercialisation

## Objective / problem

Shine-L is experiencing estate-wide database connection and PostgREST schema-cache pressure. Project L's durable-task dispatcher is not the dominant source of the cron storm, but it contributes background database traffic that is not user-facing recall.

The runtime already applies exponential backoff after claim failures and, after PR #266, coordinates lease reaping process-wide. Production still starts two independent durable claim workers.

## Technical uncertainty

It was uncertain whether Project L could halve background claim concurrency without changing:
- durable submission semantics;
- one-shot claim-token safety;
- lease and heartbeat behaviour;
- terminal persistence;
- connected-action no-replay guarantees;
- or the reusable TaskRunner contract used in tests and other call sites.

## Hypothesis / intended approach

Keep `TaskRunner`'s default at two slots, but instantiate the production server's global durable dispatcher with `slots=1`.

This reduces only live background claim/poll concurrency. All claim, retry, heartbeat, reaper and terminal-write code remains unchanged.

## Change / experiment

Modified `api/server.py`:
- production `task_runner = TaskRunner(..., slots=1)`.

Added `tests/test_durable_dispatcher_backpressure.py` proving:
1. the reusable `TaskRunner` default remains two slots;
2. production explicitly uses one slot;
3. claim exponential backoff and the #266 reaper cadence/backoff defaults remain unchanged.

## Production context

At capture time:
- PostgREST continued returning `PGRST002`;
- estate-wide cron startup timeouts remained high;
- jobs 117/119 were still observed on the old five-minute cadence because the live cadence write had not committed;
- PR #266 had merged and passed 1,753 tests but its Railway release failed before app startup at the trace-trust snapshot gate, so reaper-yield was source-ready but not yet live.

## Tests / evidence

- Branch: `project-l/single-durable-dispatcher-slot-20261001`
- CI result: **PASS — 1,756 passed, 5 warnings, 13 subtests passed in 39.25s**.
- PR #267 merged as commit `eab9b77124991271cb65ab170263c160872e4c85`.

## Learning

When a shared data plane is degraded, independent background workers should be treated as a load budget. Reducing production concurrency at the instantiation boundary can cut database demand without weakening the reusable durable-task protocol.

## Next step

The exact merged Railway deployment `8e746e9d-5a16-4eb9-b6e7-67447d994391` failed before application startup:
- Concierge fleet smoke: PASS;
- trace-trust snapshot: transient unavailable;
- bounded retries: 2s then 5s;
- terminal result: FAIL `trace-trust-snapshot-unavailable`;
- Rhee/memory/app startup were not reached.

Therefore the single-slot dispatcher is source-ready but **not yet live**. Deploy only when the Data API can pass the fail-closed trace-trust gate.

## Source artefacts

- `api/server.py`
- `tests/test_durable_dispatcher_backpressure.py`
- `.github/workflows/ci.yml`
- PR #266 durable reaper evidence
- Supabase/PostgREST outage logs

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
