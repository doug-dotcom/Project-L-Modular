# Layer 161 — Retire unbound durable task mutations

Layer 160 made verified durable tasks use request-bound heartbeats, checkpoints and terminal writes. Layer 161 removes the weaker service-role mutation capability that was kept temporarily during that rollout.

The runtime no longer exposes or calls the legacy unbound `progress` or `finish` methods. Verified tasks use only `l_task_progress_bound` and `l_task_finish_bound`. Invalid or missing claim-integrity markers fail closed before execution and, when the exact claimed row tuple is available, are recorded through the new `l_task_reject_bound` RPC.

`l_task_reject_bound` requires the current worker, stored input hash and exact JSON request to still match the running row. It is `security invoker`, uses a fixed empty `search_path`, is hidden from `public`, `anon` and `authenticated`, and is executable only by `service_role`.

The migration also revokes `service_role` execution on the old `l_task_progress` and `l_task_finish` functions. The legacy definitions remain in the schema for historical migration compatibility, but the Project L backend can no longer invoke them through Supabase.

Production database verification confirmed that the old RPCs are not executable by `service_role`, the new exact-row rejection RPC is executable by `service_role` but not `anon`, mismatched requests are rejected, and an exact invalid claim can be marked failed.

No table schema change or external dependency is introduced.
