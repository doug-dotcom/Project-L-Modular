# Layer 167 — Durable connected action journal

Layer 165 made connected action receipts request-bound and recoverable once the final answer was saved. Layer 166 propagated definitive task ownership loss cooperatively. Layer 167 closes the remaining crash window between provider confirmation and final answer persistence.

## Contract

When Google Tasks confirms creation of a task:

1. the provider receipt is constructed and semantically verified;
2. durable execution immediately records that receipt in `public.l_chat_tasks.action_receipt`;
3. the journal write is bound to the current worker, exact input hash and exact claimed request;
4. only then does capability routing continue toward the final answer;
5. the terminal durable result is accepted only when its embedded `route.action_receipt` exactly matches the durable journal.

If the journal RPC is rejected, the shared binding-loss signal is raised and the durable task stops. If the journal RPC has transport uncertainty after the provider acted, L also stops rather than exposing transport details or claiming a clean success.

## Database boundary

The additive `l_task_record_action_bound` function:

- is `security invoker`;
- uses an empty fixed `search_path`;
- verifies the receipt names the same request ID and a confirmed provider resource;
- requires the current worker, live lease, input hash and exact request JSON to match;
- writes only when the journal is empty or already contains the exact same receipt, making identical repeats idempotent and preventing replacement by a different action receipt;
- refreshes the task lease and advances the checkpoint to `connected_action_recorded`;
- is executable only by `service_role`.

The updated `l_task_finish_bound` requires journal/final-result agreement. A task with no journal may only finish without an embedded action receipt; a task with a journal may only finish with that exact receipt.

## Recovery

If a process dies after a journaled action but before the final answer is saved, recovery preserves the interrupted status and tells the user that a connected action was confirmed, instructing them to check the external service before submitting the action again.

Historical Layer 165 results that predate the journal remain readable through an explicit `legacy_unjournaled` compatibility state.

## Verification

The live migration is `20260926034242_project_l_layer167_durable_action_journal`.

A rolled-back production-database synthetic test verified:

- wrong worker and wrong input hash cannot journal;
- exact-bound journal succeeds;
- identical journal replay is idempotent;
- a different receipt cannot replace the first;
- terminal results without the journal or with a different journal are rejected;
- a matching terminal result succeeds.

Supabase security guidance was rechecked before rollout. `l_chat_tasks` continues to have RLS enabled and no browser-facing policy by design; `anon` and `authenticated` retain no table access and cannot execute the action-journal RPC.

No new external dependency is introduced.
