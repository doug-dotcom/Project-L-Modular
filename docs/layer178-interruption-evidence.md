# Layer 178 — Interruption evidence

Layer 178 makes lease-expiry interruption forensic rather than inferential.

When the bounded lease reaper moves a running task to `interrupted`, it now writes a one-time `interruption_evidence` object containing:

- evidence version;
- reason (`lease_expired`);
- interruption timestamp;
- the expired lease timestamp;
- last checkpoint;
- worker ID;
- one-shot claim token;
- whether a connected action had already been journalled.

The reaper only writes evidence when it is null, and all normal durable mutations require `status='running'`, so the evidence becomes immutable once the task is interrupted. Existing checkpoint and action receipt are preserved.

Owner-bound recovery now projects the interruption evidence alongside the existing recovery fields.

Production migrations:
- `20260926113558_project_l_layer178_interruption_evidence`
- `20260926113630_project_l_layer178_recovery_evidence_projection_v2`
