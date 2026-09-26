# Layer 170 — Reconcile ambiguous terminal-save acknowledgements

Layer 169 reconciles an ambiguous acknowledgement when a provider-confirmed connected action is journaled. Layer 170 applies the same proof-before-conclusion rule to the final durable task result.

## Contract

When L finishes a durable task:

- cognition and connected actions run only once;
- L writes the exact terminal status and result through the existing bound terminal RPC;
- if the terminal write acknowledgement is lost, L performs a read-only reconciliation before retrying;
- reconciliation requires the same request ID, worker ID, input hash, exact request JSON, terminal status and exact result JSON;
- the stored checkpoint must match the terminal status;
- connected-action journal agreement must still hold;
- a proven exact terminal row is accepted as persisted;
- if reconciliation says the terminal row is absent, only the idempotent result write may be retried;
- cognition and connected actions are never replayed;
- terminal failures use the same reconciliation path as successful answers.

## Database boundary

The additive public.l_task_confirm_finish_bound function is:

- SECURITY INVOKER;
- STABLE and read-only;
- fixed to an empty search_path;
- restricted to ready or failed status;
- exact-bound to request, worker, hash, payload and action journal;
- executable only by service_role.

The production migration is 20260926061352_project_l_layer170_reconcile_terminal_save_ack.

No external action is replayed by this layer.
