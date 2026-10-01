# Project L — R&D Daily Roll-up — 2026-10-01

## Scope

Project L memory/retrieval reliability, deployment recovery, readiness truth and Foundation isolation.

## Meaningful experiments and results

### Core operational readiness — PR #247
- Separated Railway liveness (`/health`) from core operational readiness (`/readiness`).
- Durable memory recovery is surfaced without allowing optional Foundation authority to stop Project L startup.
- CI: **1,714 passed, 5 warnings, 13 subtests**.
- First Railway deployment exposed a real memory retrieval timeout before startup; the readiness code itself was not the failure.

### Memory live-smoke transient recovery — PR #248
- Added one bounded replay only for recognised transient HTTP 503 responses carrying a valid `Retry-After`.
- Non-transient and persistent faults remain fail-closed.
- CI: **1,717 passed, 5 warnings, 13 subtests**.
- Production showed the replay logic working correctly, but the second attempt also timed out, proving a persistent database tail-latency problem rather than a smoke-script false positive.

### Indexed claim-hash memory hot path — PR #251
- Profiled the owner-bound retrieval function instead of increasing its 5-second timeout.
- Historical RPC statistics before optimisation: 260 calls; mean 1,933.5 ms; max 4,977.8 ms.
- Candidate search/scoring profile: ~221.7 ms.
- Claim hashing across 30 matching rows: ~577.8 ms.
- Excerpt hydration across four rows: ~14.2 ms.
- Evidence-index coverage: 7,288 / 7,297 owner-bound rows already had a claim hash; 0 mismatches; 9 fallback rows.
- Reused indexed claim hashes and compute content hash once only as fallback.
- Initial live migration attempt failed safely on a missing SQL function terminator; no production change occurred.
- Added explicit terminator contract, PostgreSQL rollback rehearsal returned `parse-ok`, then permanent migration applied successfully.
- CI after fix: **1,720 passed, 5 warnings, 13 subtests**.
- Post-migration public-v2 wrapper samples for the same bounded recall: **1,410.3 ms, 194.1 ms, 466.6 ms**; average ~**690.3 ms**, all status `ok`, four matches, contract v2.
- Security read-back: anon execute false; authenticated execute false; service_role execute true.

### Current-process memory circuit readiness — PR #252
- Added content-free current process state to `/readiness`.
- A current open/half-open breaker or missing database configuration cannot be masked by healthy historical recovery evidence.
- `/health` remains unchanged as forgiving Railway liveness.
- CI executable steps: **1,725 passed, 5 warnings, 13 subtests**.
- Railway deployment `d7e151e6-00e5-4753-85d8-f7da5f96121a`: **SUCCESS**.
- Production predeploy memory smoke: **PASS**, 1,988.9 ms, circuit closed, 1 record, server-verified query binding, contract v2, zero transient replay.
- Rhee live retrieval smoke: **PASS**, 9 governed evidence items, 5 lineages, server-verified contract v2.
- Live `/health`: **HTTP 200**, Foundation startup authority `active` on attempt 1.
- Live `/readiness`: **HTTP 503**, reason `memory-runtime-not-ready`.
- Readiness component truth at verification:
  - production security: ready;
  - current memory process: ready, circuit closed, failure streak 0, DB configured;
  - durable real-traffic memory: recovering;
  - historical runtime SLO: missed;
  - qualified recovery successes: 1;
  - Foundation authority: active and optional.

### Semantic background yield — PR #253
- Rebased the already-live semantic contention reduction onto current Project L main.
- Semantic activation preflight remains staggered at `2-59/15 * * * *`.
- Post-migration scheduled runs: **4.18s, 5.09s, 4.55s, 4.40s**, all successful, versus the earlier **121.07s** statement-timeout failure.
- Resource-limit helper remains fail-closed for HTTP 546 and bounded to at most 64 recent dispatch IDs before the pg_net join.
- Current-main CI: **1,729 passed, 5 warnings, 13 subtests passed in 33.11s**.
- Original stale-base PR #250 was closed as superseded by #253.

## Learning

The release is healthy and the current memory path is available, but the real-traffic recovery ledger has not yet accumulated enough latency-qualified successes to certify recovery. That historical evidence is deliberately retained rather than reset after an optimisation. Current process readiness and durable recovery history are separate signals and should remain separate.

## Next step

Allow genuine runtime use to accumulate latency-qualified memory outcomes. Keep `/health` as liveness and `/readiness` as the stricter operator truth. Do not manufacture synthetic real-traffic recovery evidence merely to turn readiness green.

## Evidence tags

R&D; AI; memory; retrieval; reliability; observability; deployment-safety; commercialisation.

## Cost record

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed in this roll-up.
