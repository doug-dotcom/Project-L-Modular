# Layer 175 — Verified and acknowledgement-safe durable submission

Layer 175 hardens the first durable boundary: getting a chat request into the queue.

The original self-verification attempt compared Python's compact canonical JSON hash with PostgreSQL `jsonb::text`. Those are different byte serialisations, so the final cutover does **not** compare those textual JSON hashes.

Instead, Project L now uses two complementary bindings:

- the existing `input_hash` remains unchanged and continues to bind the full request throughout the durable-task lifecycle;
- a new cross-language submission proof independently binds the request ID, optional conversation ID, and message using UTF-8 byte-length-prefixed fields.

Python and PostgreSQL independently compute the same `layer175-submit-v1` proof, including for non-ASCII text such as emoji.

## Lost acknowledgement recovery

`TaskStore.submit` performs the verified submit once. If the RPC response is transport-ambiguous, it does **not** blindly resubmit. It performs one read-only exact reconciliation through `l_task_confirm_submit`.

The reconciliation must match request ID, owner capability, derived user ID, full request JSON and the existing input hash. Only an exact row is accepted.

## Cutover

- runtime uses `l_task_submit_verified`;
- `l_task_confirm_submit` is read-only and service-role only;
- the legacy `l_task_submit` RPC is revoked from `service_role`;
- malformed or wrong submission proofs return `invalid`, which `/chat/start` maps to HTTP 400.

Production migrations:
- `20260926081725_project_l_layer175_self_verifying_submission` — initial database self-verification;
- `20260926081409_project_l_layer175_reconcile_submit_ack` — exact read-only submit reconciliation;
- `20260926081814_project_l_layer175_verified_submit_cutover` — corrected cross-language proof and legacy submit retirement.
