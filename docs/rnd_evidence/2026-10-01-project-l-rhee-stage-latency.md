# Project L R&D Evidence — Rhee Stage Latency Instrumentation

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Privacy-safe Rhee stage latency instrumentation
- **Tags:** R&D, AI, retrieval, Rhee, performance, observability, deployment-safety, commercialisation

## Objective / problem

After the Project L memory hot-path optimisation, the owner-scoped memory bridge canary completed in approximately 2.1 seconds, while the governed Rhee retrieval smoke still reported approximately 6.2 seconds. Rhee's existing receipt exposed only one aggregate retrieval latency, so the remaining delay could not be attributed safely to a specific stage.

## Technical uncertainty

It was uncertain whether Rhee's remaining latency was dominated by:
- identity loading;
- learning/growth context;
- owner-scoped indexed retrieval;
- raw continuity formatting;
- recent conversation loading;
- short-term loading;
- local recall ranking;
- long-term formatting;
- or the temporal-memory pass performed after the main context build.

Optimising before measuring risked changing retrieval semantics or increasing concurrent database pressure without evidence.

## Hypothesis / intended approach

Add content-free stage timing to the existing Rhee retrieval receipt without changing retrieval order, query shape, limits, ranking, evidence selection, retry policy, or privacy boundaries.

Measured stages use fixed names only:
- identity;
- learnings;
- indexed_retrieval;
- raw_continuity;
- recent_conversation;
- short_term;
- recall_ranking;
- long_term_format.

Also capture:
- total packet latency;
- temporal-memory latency;
- slowest fixed stage;
- slowest stage latency.

The live smoke prints only aggregate counts, fixed stage names and numeric durations. It does not print query text, memory text, record IDs, owner IDs or credentials.

## Change / experiment

Modified:
- `agents/rhee/rhee_v3.py` — records stage timings in `recall_plan`;
- `scripts/verify_rhee_retrieval_live.py` — reports privacy-safe total/temporal/slowest-stage metrics;
- `tests/test_rhee_retrieval_live_smoke.py` — verifies safe smoke output;
- `tests/test_rhee_stage_latency.py` — verifies actual stage measurement, failure-path partial timing and packet/temporal timing;
- `.github/workflows/ci.yml` — gates the new instrumentation tests.

## Tests / evidence

- Branch: `project-l/rhee-stage-latency-20261001`
- CI result: pending at contemporaneous capture.
- Production baseline immediately before this experiment:
  - memory bridge smoke: ~2,094 ms;
  - Rhee retrieval smoke: ~6,229 ms;
  - Rhee governed evidence: 9 items;
  - independent lineages: 5;
  - transient replays: 0.

## Failures / unexpected behaviour

None observed at the time of this contemporaneous capture. Final CI and live stage measurements must be appended from actual evidence.

## Learning

Aggregate latency alone is insufficient for safe optimisation. Rhee contains multiple independent retrieval/context stages; measuring those stages first allows the next optimisation to target the dominant cost while preserving retrieval correctness and governance.

## Next step

Run the full current Project L regression suite, merge only on green, deploy the exact runtime commit and inspect the live Rhee stage breakdown. Optimise only the measured dominant stage.

## Source artefacts

- `agents/rhee/rhee_v3.py`
- `scripts/verify_rhee_retrieval_live.py`
- `tests/test_rhee_retrieval_live_smoke.py`
- `tests/test_rhee_stage_latency.py`
- `.github/workflows/ci.yml`

## Time / cost

Engineering time is evidenced by GitHub, CI and Railway timestamps. No external monetary cost is claimed.
