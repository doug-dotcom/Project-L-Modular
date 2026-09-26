# Layer 177 — Bounded lease reaper

Layer 177 separates expired-lease maintenance from task acquisition.

Previously every call to `l_task_claim_bound` first updated every expired running task to `interrupted`. The no-replay behaviour was correct, but a single worker polling for one queued task had global mutation scope.

Layer 177 introduces `l_task_reap_expired(limit)`, a backend-only bounded maintenance RPC using `FOR UPDATE SKIP LOCKED`. The requested batch is clamped to 1–500 rows and defaults to 100. The dispatcher explicitly reaps before attempting a claim.

`l_task_claim_bound` no longer performs a global expiry sweep. Its mutation scope is now limited to the one task it claims.

Production migration: `20260926084955_project_l_layer177_bounded_lease_reaper`.
