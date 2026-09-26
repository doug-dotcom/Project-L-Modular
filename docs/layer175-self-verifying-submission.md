# Layer 175 — Self-verifying durable submission

The durable queue now verifies request identity at the database entry point. Before insertion, `l_task_submit` checks the embedded request ID, validates owner/hash shapes, and independently recomputes SHA-256 over PostgreSQL's canonical JSONB text. A mismatched caller-supplied hash is rejected before insertion. Existing request IDs must match the exact stored request JSON as well as the stored hash.

The RPC remains SECURITY INVOKER and service-role only.

Production migration: `20260926081725_project_l_layer175_self_verifying_submission`.
