# Layer 169 — Reconcile ambiguous action-journal acknowledgements

Layer 167 made connected actions durable before final answer persistence. Layer 168 preserved the exact durable receipt when execution later failed. Layer 169 closes the acknowledgement ambiguity that remains when the provider action succeeds, the journal write commits, but the journal RPC response is lost in transit.

## Contract

When a connected action has already been confirmed by the provider:

- L attempts the normal exact-bound durable journal write once;
- if that RPC returns normally, the existing Layer 167 path is unchanged;
- if the RPC response is transport-ambiguous, L never replays the provider action and never retries the journal mutation;
- L performs one read-only reconciliation against the exact request ID, worker, input hash, claimed request JSON and frozen action receipt;
- only an exact live match is accepted as proof that the journal committed;
- an absent, different, expired or otherwise unbound journal remains fail-closed;
- reconciliation transport failure also remains fail-closed and does not expose transport details.

A successful reconciliation is therefore evidence of the already-committed journal, not a guess and not a second write.

## Database boundary

The additive public.l_task_confirm_action_bound function:

- is security invoker with an empty fixed search_path;
- is STABLE and read-only;
- requires the task to still be running under the same live lease;
- binds request ID, worker ID, input hash, exact request JSON and exact action receipt;
- is executable only by service_role;
- leaves l_chat_tasks RLS and browser access unchanged.

The production migration is 20260926051707_project_l_layer169_reconcile_action_journal_ack.

No external action is replayed by this layer.
