# Layer 173 — Harden pre-execution rejection

Layer 173 closes the remaining terminal-state bypass in the durable task RPC surface.

`l_task_finish_bound` already enforces exact request binding and connected-action journal agreement. The older `l_task_reject_bound` was intentionally created for a different purpose: marking an invalid claimed request as failed before any execution begins. Its database predicate, however, previously allowed any exact-bound running task to be failed through that RPC.

## Contract

`public.l_task_reject_bound` is now explicitly a pre-execution-only operation.

A rejection succeeds only when all of the following are true:

- request ID, worker, input hash and exact request JSON still match;
- the lease is still live;
- the claim is token-bound;
- status is still `running`;
- checkpoint is exactly `starting`;
- no result has previously been stored;
- no connected-action journal exists;
- the rejection payload is a JSON object with a textual reply;
- the payload explicitly contains `"error": true`;
- the payload contains no connected-action receipt.

Once execution advances beyond `starting`, or any provider-confirmed action is journaled, this RPC can no longer terminally mutate the task. Normal terminal persistence must go through the Layer 167/170 finish path.

## Database boundary

The RPC remains:

- SECURITY INVOKER;
- fixed to an empty search_path;
- inaccessible to public, anon and authenticated;
- executable only by service_role.

The production migration is `20260926074116_project_l_layer173_harden_preexecution_reject`.
