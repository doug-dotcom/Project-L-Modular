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
- CI state at contemporaneous capture: **in progress**
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

## Learning

A fail-closed health gate is more operationally useful when it exposes the evidence required to clear itself. Recovery certification should be auditable and deterministic, not an opaque boolean.

## Next step

Complete the full Project L regression suite, merge only on green, deploy the exact runtime commit, and verify the live `/readiness` response reports the certification gap without changing its HTTP status or counting canaries.

## Source artefacts

- `orchestration/lieutenants/observability_lieutenant.py`
- `core/cognition/operational_readiness.py`
- `tests/test_observability_lieutenant.py`
- `tests/test_operational_readiness.py`
- PR #254
- CI run `36811713985`

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
