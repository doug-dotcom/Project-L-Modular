# Layer 160 — Bind durable mutations to the claimed request

Layer 159 verifies a durable request when the worker claims it. Layer 160 extends that guarantee across the rest of the task lifecycle so the database request cannot be changed after claim and still receive heartbeats, checkpoints or a completed result.

Two additive service-role-only RPCs now bind each mutation to the exact request body and input hash returned by the claim:

- `l_task_progress_bound` renews the lease or advances a checkpoint only when the row still has the claimed request and input hash.
- `l_task_finish_bound` writes a ready/failed result only when the row still has the claimed request and input hash.

The runner freezes a private snapshot of the verified claim, then uses these bound RPCs for action checkpoints, heartbeats, successful results and execution-failure results. If a bound write is rejected, the runner does not fall back to the older unbound mutation path. Direct pre-contract test fixtures remain compatible through the legacy methods.

The database migration is additive, uses `security invoker`, fixes `search_path`, revokes execution from `public`, `anon` and `authenticated`, and grants only `service_role`. The existing unbound RPCs remain temporarily available so the already-running Layer 159 deployment is not broken during rollout.

Production verification used rolled-back synthetic rows: wrong hashes and wrong request bodies were rejected, exact bound progress succeeded, and a request changed during work could not accept the final result.

No table schema change or external dependency is introduced.
