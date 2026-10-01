# Project L R&D Evidence — Trace-Trust Snapshot Recovery

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Trace-trust predeploy snapshot recovery
- **Tags:** R&D, AI, trust, Supabase, PostgREST, reliability, deployment-safety, commercialisation

## Objective / problem

Two Project L profiler deployments failed before Rhee ran because the Shine-AI trace-trust predeploy smoke received `trace-trust-snapshot-unavailable`.

Supabase logs for the latest failed release showed repeated HTTP 503 responses from `shine_ai_trace_trust_snapshot_v3`, PostgreSQL `57014 canceling statement due to statement timeout`, and PostgREST failing to refresh its schema cache. This occurred during shared-database saturation rather than a cryptographic/quorum trust mismatch.

## Technical uncertainty

It was uncertain whether the trust gate could tolerate a short PostgREST/schema-cache recovery window without weakening the fail-closed trust model.

The critical distinction is:
- `trace-trust-snapshot-unavailable` means the snapshot RPC could not be read;
- cryptographic, policy, quorum, witness, checkpoint and chain failures all have distinct reason codes.

## Hypothesis / intended approach

Retry only the exact transport/snapshot-unavailable reason.

Use two bounded waits:
- first replay after 2 seconds;
- second and final replay after 5 seconds.

All other trust failures return immediately without replay. The retry does not bypass validation; each successful snapshot still has to pass the full existing authenticated storage, quorum, roster, witness, chain and checkpoint checks.

## Change / experiment

Modified `scripts/verify_shine_ai_trace_trust.py`:
- added `TRACE_SNAPSHOT_TRANSIENT_REASON = "trace-trust-snapshot-unavailable"`;
- added retry delays `(2.0, 5.0)`;
- wrapped the seal/snapshot read and verification-keyset read in bounded recovery helpers;
- resets only the local keyset cache between attempts;
- records content-free retry count in PASS output;
- keeps all non-transient trust errors fail-closed.

Added regression tests proving:
1. two transient snapshot failures can recover on the third attempt;
2. a cryptographic/chain-style failure is not retried;
3. verification-keyset snapshot recovery is bounded;
4. only the exact snapshot-unavailable reason is named as retryable.

## Production evidence

Latest failed profiler release `2c5281e8-3d5a-4433-bb15-4815f3b9ff0b`:
- Concierge fleet smoke: PASS;
- Shine-AI trace trust smoke: FAIL `trace-trust-snapshot-unavailable`;
- Rhee never executed.

Supabase during the same window:
- repeated HTTP 503 on `/rpc/shine_ai_trace_trust_snapshot_v3`;
- PostgreSQL SQLSTATE `57014`;
- PostgREST schema-cache refresh timeout.

The semantic worker backpressure fix from #256 is already live as Edge Function version 7, reducing the writer amplification that contributed to the saturation.

## Tests / evidence

- Branch: `project-l/trace-trust-snapshot-recovery-20261001`
- CI result: pending at contemporaneous capture.
- Live deployment verification must be appended from actual evidence.

## Learning

Security gates should fail closed on invalid trust evidence, but an unavailable transport is a different class from invalid evidence. A bounded wait for infrastructure recovery can improve deployment reliability without accepting any unverified trust state.

## Next step

Run the complete Project L regression suite, merge only on green, deploy the exact runtime commit, then verify:
- trace-trust smoke either passes directly or reports a bounded snapshot replay;
- memory smoke passes;
- Rhee profiler finally executes and reveals the dominant latency stage;
- Railway reaches terminal SUCCESS.

## Source artefacts

- `scripts/verify_shine_ai_trace_trust.py`
- `tests/test_shine_trace_trust_smoke_contract.py`
- Supabase PostgreSQL/PostgREST logs
- failed Railway profiler deployments
- live `l-semantic-worker` Edge Function version 7

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
