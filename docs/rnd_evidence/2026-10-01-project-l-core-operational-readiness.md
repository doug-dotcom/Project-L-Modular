# Project L R&D Evidence — Core Operational Readiness

- **Project:** Project L
- **Captured:** 2026-10-01 12:20:33 AEST (2026-10-01T02:20:33Z)
- **Build:** Core operational readiness contract
- **R&D / commercialisation tags:** R&D, AI, memory, reliability, observability, deployment-safety, commercialisation

## Objective / problem

Project L's existing `/health` endpoint is intentionally a liveness signal for Railway. It confirms the process and production security boundary are alive, but it does not distinguish a live process from a core memory runtime that is currently recovering or degraded. The previous Foundation incident reinforced that optional integrations must not take standalone L down, while core memory failures still need a truthful operator signal.

## Technical uncertainty

It was uncertain whether Project L could expose current memory readiness without:
1. causing Railway restart loops during transient memory recovery;
2. incorrectly treating historical memory SLO failures as current unavailability after a healthy recovery streak;
3. allowing optional Foundation authority state to block standalone Project L;
4. exposing private memory/user content through operational telemetry.

## Hypothesis / intended approach

Keep `/health` as a stable liveness probe and introduce a separate public `/readiness` contract derived only from privacy-safe memory SLO telemetry, production security state and content-free Foundation authority state.

Expected behaviour:
- production security remains fail-closed;
- memory `healthy` or `recovered_observing` is ready;
- memory `warming` remains serviceable while evidence accumulates;
- memory `recovering`, `degraded` or unknown is not ready;
- optional Foundation authority is visible but never gates standalone L readiness;
- historical SLO `missed` does not override a current `recovered_observing` state.

## Change / experiment

Implemented:
- `core/cognition/operational_readiness.py` — pure readiness classifier;
- `GET /readiness` in `api/server.py`;
- public-route and runtime-provenance handling for `/readiness`;
- no change to Railway's existing `/health` liveness healthcheck;
- `tests/test_operational_readiness.py` covering healthy recovery, warming, recovering, degraded, missing telemetry and production-security blocking;
- CI wiring for the new test module.

The readiness payload contains operational states and counts only. It does not include memory content, prompts, queries, owner IDs, user IDs, credentials or tokens.

## Tests / evidence

- Pull request: #247 — **Add core operational readiness contract**
- Initial head: `680fde19f561650720ccaa896ea9e981d7467da8`
- CI workflow run: `36805386337`
- CI state at contemporaneous capture: **in progress**
- Syntax, dependency import and Shine Defence sensitive-memory certification gates are included before the full regression suite.

## Failures / unexpected behaviour

No implementation failure had been observed at the time of this contemporaneous capture. Final regression and live deployment results must be appended from actual evidence; they must not be inferred.

## Learning

Liveness and readiness are materially different reliability signals. Project L should remain alive through recoverable dependency incidents, while a separate readiness signal reports whether its core memory path is presently suitable to serve. Current recovery evidence should be represented independently from lifetime SLO history.

## Next step

Run the complete active Project L regression suite, merge only on a green result, deploy the exact merged commit, and verify the live `/readiness` response independently of `/health`.

## Source artefacts

- Branch: `project-l/core-operational-readiness-20261001`
- `core/cognition/operational_readiness.py`
- `api/server.py`
- `tests/test_operational_readiness.py`
- `.github/workflows/ci.yml`
- PR #247
- CI run `36805386337`

## Time / cost

Engineering time is represented by contemporaneous GitHub commit, PR, CI and deployment timestamps. No external monetary cost is claimed in this receipt.
