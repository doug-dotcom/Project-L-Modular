# Project L R&D Evidence — Semantic Worker Transient Yield

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Semantic embedding worker transient-write backpressure
- **Tags:** R&D, AI, memory, embeddings, PostgreSQL, Supabase, backpressure, reliability, deployment-safety, commercialisation

## Objective / problem

A Project L deployment containing Rhee stage-latency instrumentation failed before Rhee executed because the Shine-AI trace-trust smoke could not read its Supabase snapshot. An independent Supabase SQL read also timed out. Database logs showed repeated PostgreSQL `57014` statement timeouts and PostgREST timeout-manager kills.

The strongest repeated pattern was inside the semantic embedding worker:
1. `project_l_complete_semantic_unit_v1` timed out while writing `private.l_memory_semantic_units`;
2. the Edge Function catch block immediately called `project_l_fail_semantic_unit_v1` against the same busy table;
3. that failure-persistence write also timed out.

This doubled write pressure during an already-saturated interval.

## Technical uncertainty

It was uncertain whether transient completion failures could safely yield without:
- falsely marking units failed;
- losing ownership safety;
- changing claim/retry semantics;
- increasing batch sizes;
- or silently treating non-transient embedding/database failures as success.

## Hypothesis / intended approach

For exact transient database codes already recognised by the worker (`57014`, `PGRST002`, `PGRST003`):
- a **claim** failure retains the existing bounded retry/defer behaviour;
- a **completion** failure should return HTTP 202 `deferred` immediately rather than issuing a failure write;
- if persistence of a genuine non-transient failure itself hits a transient database error, return HTTP 202 `deferred` rather than retrying/hammering;
- the claimed row remains protected by its existing lease and can recover after lease expiry.

Non-transient completion errors still enter the existing failure path.

## Change / experiment

Modified `supabase/functions/l-semantic-worker/index.ts`:
- generalised the transient code set to database operations, not only claims;
- added bounded error-code classification;
- added a fixed, content-free `deferredBody()` response;
- transient eval completion → `202 deferred / eval_complete`;
- transient semantic-unit completion → `202 deferred / unit_complete`;
- transient eval failure-persistence → `202 deferred / eval_failure_persist`;
- transient unit failure-persistence → `202 deferred / unit_failure_persist`;
- deferred responses state `leaseRecovery: expiry`;
- default work limits remain unchanged: eval 8 (max 16), unit batch 16 (max 32);
- claim retry delay remains 350 ms.

No memory text, embedding vector, query text, owner identifier or worker token is added to logs/responses.

## Production evidence that triggered the experiment

Around 2026-10-01 04:00 UTC:
- direct Supabase SQL access from the agent timed out twice;
- PostgREST logged multiple `Warp server error: Thread killed by timeout manager`;
- `project_l_complete_semantic_unit_v1` produced SQLSTATE `57014`;
- `project_l_fail_semantic_unit_v1` then also produced SQLSTATE `57014`;
- a separate `me_activation_operational_episode_v1` read timed out, confirming shared database pressure rather than a single-RPC code defect;
- Railway predeploy failed at `Shine-AI trace trust smoke: FAIL trace-trust-snapshot-unavailable` before Rhee instrumentation ran.

The live `l-semantic-worker` Edge Function version 6 matched repository source exactly before modification.

## Tests / evidence

- Branch: `project-l/semantic-worker-transient-yield-20261001`
- New contract tests: `tests/test_semantic_worker_transient_yield.py`
- CI result: pending at contemporaneous capture.
- Live Edge Function deployment and post-change database behaviour must be recorded from actual evidence.

## Failures / unexpected behaviour

The Rhee profiler deployment could not be used for latency diagnosis because shared database saturation stopped predeploy earlier at the trace-trust snapshot. That failure redirected this experiment to the more fundamental backpressure problem.

## Learning

Backpressure must extend through the **write-completion path**, not only the claim path. A transient completion timeout followed immediately by a failure write is positive feedback: the worker increases load precisely when the database is signalling saturation.

## Next step

Run the full Project L regression suite, deploy the exact Edge Function source if green, verify the live function version, observe whether transient completion errors now yield instead of producing paired failure-write timeouts, then redeploy the Rhee profiler after the database stabilises.

## Source artefacts

- `supabase/functions/l-semantic-worker/index.ts`
- `tests/test_semantic_worker_transient_yield.py`
- Project L Supabase PostgreSQL/PostgREST logs
- failed Railway deployment `48667375-b269-4e78-be85-6805b0a88dfe`

## Time / cost

Engineering time is evidenced by GitHub, Supabase and Railway timestamps. No external monetary cost is claimed.
