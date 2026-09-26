# Layer 172 — Retire the legacy unbound claimant

Layer 171 moved the Project L dispatcher to one-shot token-bound claims. Layer 172 removes the remaining runtime bypass: the original public.l_task_claim(worker) RPC is no longer executable by service_role.

## Why this matters

The legacy claimant predates claim tokens. Leaving it executable would allow backend code to bypass:

- one-shot claim identity;
- exact replay of an ambiguous claim;
- the rule that a worker cannot silently substitute another queued task after an uncertain response.

Project L no longer calls that RPC, but an unused privileged path is still a privileged path. Layer 172 closes it.

## Contract

- public.l_task_claim(uuid) remains present only for migration-history compatibility and is explicitly marked retired;
- public, anon, authenticated and service_role cannot execute the legacy claimant;
- public.l_task_claim_bound(uuid, uuid) remains the only service-role claim RPC;
- production runtime contains no call to the legacy claimant;
- durable SQL regression tests use only token-bound claims;
- the existing one-running-task-per-worker and unique claim-token constraints remain unchanged.

The production migration is 20260926072827_project_l_layer172_retire_legacy_claim.
