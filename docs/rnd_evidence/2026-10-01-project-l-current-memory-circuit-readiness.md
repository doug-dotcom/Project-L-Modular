# Project L R&D Evidence — Current Memory Circuit Readiness

- **Project:** Project L
- **Captured:** 2026-10-01 AEST
- **Build:** Current-process memory circuit readiness
- **Tags:** R&D, AI, memory, reliability, observability, deployment-safety, commercialisation

## Objective / problem

Project L's new `/readiness` endpoint correctly separates Railway liveness from durable memory runtime readiness, but the production timeout investigation exposed a remaining blind spot: durable history can report `recovered_observing` while the current Project L process has just opened its memory circuit breaker because the live RPC failed.

## Technical uncertainty

It was uncertain whether current circuit state could be added to readiness without:
1. causing a new database call from `/readiness`;
2. exposing memory content, user identifiers, credentials or query material;
3. changing Railway's forgiving `/health` liveness contract;
4. allowing an optional Foundation state to block standalone Project L.

## Hypothesis / intended approach

Reuse the memory bridge's existing process-local, content-free circuit snapshot. Gate readiness on:
- database configured;
- process status `ready`;
- circuit state `closed`.

An open or half-open breaker should return HTTP 503 from `/readiness` even if durable memory history is `healthy` or `recovered_observing`. Railway `/health` remains unchanged.

## Change / experiment

Implemented:
- public content-free helper `memory_bridge_process_snapshot()` in `api/shine_ai_memory.py`;
- current-process memory component in `core/cognition/operational_readiness.py`;
- server wiring in `api/server.py`;
- readiness precedence: production security → current memory process → durable memory → optional Foundation;
- regression cases for open breaker, half-open recovery probe, missing DB configuration and missing process snapshot.

The process snapshot contains only:
- status;
- circuit state;
- retry delay;
- failure streak;
- whether a recovery probe is in progress;
- whether database configuration exists.

It does not query Supabase and contains no memory, prompt, query, owner, user or credential content.

## Tests / evidence

- Pull request: #252 — **Gate readiness on current memory circuit state**
- Initial head: `f1c78a3e30b46f2d5a731c3bdc92a5ae519bb0f7`
- CI workflow run: `36807693145`
- Syntax, dependency-import and Shine Defence sensitive-memory gates: **PASS**
- Full regression state at contemporaneous capture: **in progress**

## Failure / unexpected behaviour that motivated the layer

The earlier readiness deployment exposed repeated memory RPC timeout/circuit-breaker behaviour. The durable SLO ledger is intentionally historical, so it cannot by itself represent a breaker that opened moments ago in the current process.

## Learning

Historical reliability evidence and current process protection state answer different questions. A truthful readiness contract must require both: durable evidence says whether memory has recovered over time; the local circuit says whether this process should serve memory traffic right now.

## Next step

Complete the full regression suite, merge only on green, deploy the exact runtime commit, and verify live:
- predeploy memory smoke passes against the indexed-hash DB optimisation;
- `/health` returns 200;
- Foundation authority reaches active;
- `/readiness` returns current process and durable memory components without private content.

## Source artefacts

- `api/shine_ai_memory.py`
- `core/cognition/operational_readiness.py`
- `api/server.py`
- `tests/test_operational_readiness.py`
- PR #252
- CI run `36807693145`

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
