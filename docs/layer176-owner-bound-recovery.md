# Layer 176 — Owner-bound durable recovery

Layer 176 hardens the read side of Project L's durable task lifecycle.

Before this layer, `TaskStore.get` used the service-role table client directly and assembled the recovery ownership predicates in application code. The returned row was then extensively verified for request, delivery, provenance, connected-action and document-evidence integrity.

Layer 176 moves the recovery authorization boundary into one backend-only PostgreSQL RPC.

## Contract

`l_task_recover_bound` returns a row only when:

- request ID matches;
- derived user ID matches;
- recovery-owner hash matches;
- the owner hash has the expected 64-character lowercase hexadecimal shape.

The RPC exposes only the fields needed by Project L's existing recovery-integrity pipeline.

It is:

- SECURITY INVOKER;
- STABLE and read-only;
- fixed to an empty search path;
- unavailable to public, anon and authenticated;
- executable only by service_role.

The existing request, journal, delivery, provenance, action-receipt and document-evidence verification still runs after the bound read.

Production migration: `20260926084112_project_l_layer176_owner_bound_recovery`.
