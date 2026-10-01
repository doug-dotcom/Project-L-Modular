# Project L R&D Evidence — Recovery Certification Explainability

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Durable memory recovery certification explainability
- **Tags:** R&D, AI, memory, reliability, observability, deployment-safety, commercialisation

## Objective / problem

Project L's `/readiness` endpoint correctly remained HTTP 503 after the live memory path recovered because the durable real-traffic ledger had only one latency-qualified success since the previous failures. The gate was correct, but its public evidence was incomplete: it exposed the current qualified count without exposing the required threshold, remaining evidence, latency target or the current blocker.

## Technical uncertainty

It was uncertain whether the recovery gate could become self-explaining without:
1. changing the existing certification threshold;
2. counting deployment canaries or synthetic traffic as real recovery evidence;
3. exposing private memory or user data;
4. weakening fail-closed readiness behaviour.

## Hypothesis / intended approach

Keep the recovery rule unchanged at **three latency-qualified real-traffic successes since the latest failure**, but make the rule explicit and machine-readable.

Expose only content-free certification metadata:
- required qualified successes;
- current qualified successes;
- successes remaining;
- certification flag;
- blocker category;
- latency target;
- latest real-traffic recovery latency.

## Change / experiment

Changes:
- replaced the inline magic threshold `3` with `MEMORY_RECOVERY_REQUIRED_QUALIFIED_SUCCESSES = 3`;
- added explicit recovery certification progress to the durable memory SLO snapshot;
- added blocker categories:
  - `none`;
  - `needs-qualified-successes`;
  - `latest-failure`;
  - `latency-above-target`;
  - `missing-latency`;
  - `no-clean-runtime-samples`;
- surfaced those fields through `/readiness`;
- preserved canary exclusion and existing runtime/deployment SLO history.

## Tests / evidence

- PR #254 — **Explain memory recovery certification in readiness**
- Initial head: `939868ed5e7974ba4488877362c7bb1c04babf30`
- CI workflow run: `36811713985`
- First full-suite attempt exposed two fixture assumptions about warm-up precedence: **2 failed, 1,731 passed, 5 warnings, 13 subtests**.
- Investigation confirmed the pre-existing contract intentionally keeps `operational_state=warming` below 20 lifetime runtime samples, even while recovery metadata is visible.
- Test fixtures were corrected to model the production condition (20+ historical samples) rather than changing warm-up semantics.
- Final CI run `36811988983` on head `70c11dd286a55c9c944b813fc3e4b8e4c6d70ae4`: **PASS — 1,734 passed, 5 warnings, 13 subtests passed in 34.00s**.
- New tests cover:
  - one qualified success → two remaining;
  - latency above 3,000 ms → latency blocker;
  - three clean qualified successes → certification earned;
  - readiness payload exposes the certification gap.

## Production context

Immediately before this layer:
- current memory process: ready;
- circuit: closed;
- failure streak: 0;
- durable runtime: recovering;
- qualified recovery successes: 1;
- historical runtime SLO: missed;
- Foundation authority: active;
- `/health`: 200;
- `/readiness`: 503 `memory-runtime-not-ready`.

No synthetic recovery traffic is introduced by this change.

## Failures / unexpected behaviour

The first regression run failed because two new tests expected `recovering` / `degraded` operational states with fewer than the 20 samples required to leave the established warm-up phase. Existing tests explicitly preserve `warming` precedence during that baseline period. The product semantics were left unchanged; the new fixtures were corrected to represent post-baseline production recovery.

## Live production proof

- PR #254 merged as `354e1442bcd53785a1df4099d76efb9e804484ea`.
- Railway deployment `62bf6d85-65a8-4e3e-827d-7b0ba050ecf3`: **SUCCESS**.
- Memory live smoke: **PASS**, circuit closed, 2,094.4 ms, zero transient replays.
- Rhee live smoke: **PASS**, 9 governed evidence items, 5 lineages, server-verified contract v2.
- External `/health`: **HTTP 200**.
- Foundation startup authority: **active**, attempt 1.
- External `/readiness`: **HTTP 503** `memory-runtime-not-ready`, with:
  - current memory process ready;
  - circuit closed;
  - failure streak 0;
  - qualified recovery successes **1**;
  - required qualified successes **3**;
  - qualified successes remaining **2**;
  - recovery certified **false**;
  - blocker `needs-qualified-successes`;
  - latency target **3,000 ms**;
  - latest real-traffic recovery latency **2,133.1 ms**.

No canary or synthetic traffic was counted toward recovery certification.

## Learning

A fail-closed health gate is more operationally useful when it exposes the evidence required to clear itself. Recovery certification should be auditable and deterministic, not an opaque boolean. Warm-up baseline semantics and post-failure recovery certification are separate concepts and should remain separate.

## Next step

Allow genuine runtime use to earn the remaining two qualified successes. Do not manufacture recovery traffic or reset historical evidence merely to turn readiness green.

## Source artefacts

- `orchestration/lieutenants/observability_lieutenant.py`
- `core/cognition/operational_readiness.py`
- `tests/test_observability_lieutenant.py`
- `tests/test_operational_readiness.py`
- PR #254
- CI run `36811713985`

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
