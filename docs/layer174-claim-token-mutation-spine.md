# Layer 174 — Claim-token mutation spine

Layer 174 carries the one-shot claim identity through every post-claim durable mutation.

When `l_task_claim_bound` returns a task, `TaskStore` verifies that the returned `claim_token` exactly matches the requested token and remembers it per worker. Every later durable mutation then supplies that exact token to Postgres:

- heartbeat and checkpoint renewal;
- connected-action journal writes;
- ambiguous action-journal reconciliation;
- pre-execution rejection;
- terminal result persistence;
- ambiguous terminal-save reconciliation.

A missing, malformed or mismatched claim token fails closed before a post-claim mutation can succeed. Successful terminal save, confirmed terminal save, or pre-execution rejection clears the process-local worker-to-token binding.

## Safe rollout

Layer 174 used a two-stage production cutover:

1. `20260926075023_project_l_layer174_claim_token_mutation_spine` added the token-bound RPC generation while the previous bound RPCs remained available.
2. Project L runtime was switched to the new RPCs, passed CI, and Railway production was verified live on the new runtime.
3. `20260926080813_project_l_layer174_retire_tokenless_bound_mutations` then revoked `service_role` execution from all six tokenless post-claim RPCs.

The older functions remain only as migration-history artefacts and are explicitly marked retired. The claim-token-bound RPCs are now the only authorised post-claim mutation surface.
