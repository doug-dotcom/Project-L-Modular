# Project L R&D Evidence — Memory Smoke Transient Recovery

- **Project:** Project L
- **Captured:** 2026-10-01 12:28 AEST
- **Build:** Memory-bridge live-smoke transient replay hardening
- **Tags:** R&D, AI, memory, reliability, deployment-safety, observability, commercialisation

## Objective / problem

The Project L readiness layer passed the full regression suite, but its first Railway deployment failed before startup because the production memory-bridge predeploy smoke received a recoverable HTTP 503 `retrieval-unavailable` after approximately 12.3 seconds. The bridge itself already had a circuit breaker and a `Retry-After` recovery contract, but the smoke ignored that contract and failed immediately.

## Technical uncertainty

It was uncertain whether the deployment smoke could tolerate a narrow, known transient recovery window without weakening fail-closed behaviour for authentication, configuration, permission, contract or persistent availability failures.

## Hypothesis / intended approach

Allow exactly one replay only when all of the following are true:
- HTTP status is 503;
- the response detail matches a known transient bridge condition;
- a valid positive `Retry-After` value is present.

Wait for `Retry-After + 0.25s`, capped at 10 seconds. Any non-transient failure fails immediately. A second transient failure also fails closed.

## Change / experiment

Modified `scripts/verify_memory_bridge_live.py` to:
- classify only known transient 503 responses;
- perform at most one bounded replay;
- record `transient_replays` in PASS output and content-free SLO evidence;
- keep all memory content, query text, owner IDs and credentials out of logs.

Added regression coverage proving:
1. one transient 503 succeeds on replay;
2. a non-transient 503 is not retried;
3. a persistent transient fails after exactly one replay.

## Tests / evidence

- Pull request: #248 — **Honor memory bridge transient recovery in live smoke**
- Head before merge: `54bd46e348c5fcfdffb7ece56b0989eeca02e1e4`
- CI workflow run: `36805911875`
- CI result: **PASS — 1,717 passed, 5 warnings, 13 subtests passed in 31.19s**
- Syntax, dependency imports and Shine Defence sensitive-memory certification: **PASS**

## Failure / unexpected behaviour that triggered this work

Railway deployment `f72af43c-116b-4e70-9550-df6796c8c7fa` for readiness PR #247 failed before startup because the memory live smoke recorded `SHINE_AI_MEMORY_SLO outcome=failure latency_ms=12299.1` and `FAIL retrieval-unavailable`.

## Learning

Deployment verification should respect the recovery semantics of the dependency it is verifying. A circuit-breaker-protected dependency can be temporarily unavailable by design; the release gate should tolerate one bounded recovery attempt while still failing closed on persistent or non-transient faults.

## Next step

Merge #248, allow Railway to redeploy the readiness commit plus smoke hardening, and verify:
- predeploy memory smoke passes;
- `/health` remains 200;
- Foundation startup authority reaches active;
- the new `/readiness` endpoint returns a truthful current status.

## Source artefacts

- `scripts/verify_memory_bridge_live.py`
- `tests/test_memory_bridge_live_smoke_contract.py`
- PR #248
- CI run `36805911875`
- Failed deployment `f72af43c-116b-4e70-9550-df6796c8c7fa`

## Time / cost

Engineering time is evidenced by GitHub, CI and Railway timestamps. No external monetary cost is claimed.
