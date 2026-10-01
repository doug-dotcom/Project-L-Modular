# Project L R&D Evidence — Indexed Claim Hash Retrieval Hot Path

- **Project:** Project L
- **Captured:** 2026-10-01 12:42 AEST
- **Build:** Owner-scoped memory retrieval indexed claim-hash optimisation
- **Tags:** R&D, AI, memory, retrieval, performance, reliability, deployment-safety, commercialisation

## Objective / problem

Project L's readiness release remained blocked by the production memory-bridge predeploy smoke. The bounded transient replay added in PR #248 behaved correctly, but the second attempt also timed out. Hosted PostgreSQL logs confirmed SQLSTATE 57014 statement timeouts in the owner-scoped memory retrieval function, so the issue was not merely Railway transport noise.

## Technical uncertainty

It was uncertain whether the 5-second tail latency was caused by:
- full-text candidate search;
- owner/evidence/quarantine joins;
- claim-deduplication hashing;
- excerpt hydration;
- or general database load.

The goal was to reduce hot-path work without changing ranking, dedupe, owner binding, correction precedence, permissions, or the existing 5-second fail-closed statement timeout.

## Evidence / profiling

Observed production evidence:
- Railway readiness deployment #247 failed memory smoke at approximately 12.3s total.
- #248 retried once according to the bridge Retry-After contract, then also failed.
- Supabase logs showed SQLSTATE `57014` / `canceling statement due to statement timeout`.
- `pg_stat_statements` for the PostgREST RPC: 260 calls, mean execution 1,933.5ms, minimum 206.6ms, maximum 4,977.8ms.
- Candidate search/scoring profile for the same `diving bali` query: approximately 221.7ms execution, 24 ranked rows, 866 shared buffer hits.
- Claim SHA-256 calculation across 30 matching rows: approximately 577.8ms.
- Excerpt hydration across four rows: approximately 14.2ms.
- Owner-bound catalog coverage: 7,297 rows.
- Existing evidence-index claim hashes: 7,288 rows.
- Missing indexed hashes: 9 rows.
- Indexed hash mismatches against `private.project_l_claim_hash_v1(content)`: 0.

## Hypothesis / intended approach

The existing retrieval query computes `project_l_claim_hash_v1(content)` twice per bounded candidate: once for the projected diversity hash and again for the window partition. The query already joins `private.l_memory_evidence_index`, which contains the same owner-bound claim hash for almost every base memory.

Use:
`coalesce(indexed_claim_hash, project_l_claim_hash_v1(content))`

in one materialized `claim_hashed` stage, then partition by that computed alias. Base memories use the indexed value; corrected overlays and the nine unindexed rows retain a compute-once fallback.

## Change / experiment

Added migration:
`supabase/migrations/20261001024500_optimize_project_l_memory_claim_hash.sql`

Key changes:
- project `e.claim_hash` as `indexed_claim_hash` for base candidates;
- corrected candidates deliberately use `NULL` so corrected content is hashed independently;
- add a materialized `claim_hashed` stage;
- compute the content hash at most once as fallback;
- remove duplicate SHA-256 work from the window partition;
- preserve the 5-second statement timeout;
- preserve SECURITY DEFINER, empty search_path and service-role-only execution.

Added CI contract coverage in:
`tests/test_memory_claim_hash_hotpath_contract.py`.

## Tests / evidence

- PR #251 — **Reuse indexed claim hashes in memory retrieval hot path**
- Initial head: `14439d2af676a925380305f9ba7deaba4d590ea1`
- CI workflow: `36807073833`
- CI state at contemporaneous capture: **in progress**
- Pre-regression gates for syntax, imports and Shine Defence sensitive-memory boundary: **PASS**

## Failures / unexpected behaviour

The first readiness deploy and the first bounded-replay deploy both failed before application startup due to memory retrieval timeouts. The bounded replay itself behaved correctly; persistent timeout proved the release gate was exposing a real retrieval tail-latency problem.

## Learning

The full-text search is not the dominant cost for this query. Repeated content hashing on already-indexed evidence is avoidable hot-path work. Precomputed evidence should be reused when its parity with the canonical calculation is verified and a safe fallback remains for missing/corrected rows.

## Next step

After CI passes:
1. apply the exact migration live;
2. verify indexed-hash parity remains intact;
3. benchmark the same owner-bound query with content suppressed;
4. redeploy Project L and prove the predeploy memory smoke, `/health`, Foundation authority and `/readiness` all succeed.

## Source artefacts

- PR #251
- CI run `36807073833`
- `supabase/migrations/20261001024500_optimize_project_l_memory_claim_hash.sql`
- `tests/test_memory_claim_hash_hotpath_contract.py`
- Railway failed deployments from #247/#248
- Supabase PostgreSQL/PostgREST logs and `pg_stat_statements` measurements

## Time / cost

Engineering time is evidenced by GitHub, CI, Railway and Supabase timestamps. No external monetary cost is claimed.
