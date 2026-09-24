# Layer 111 — Durable Task Ledger Audit

Layers 108–110 verify saved-answer recovery. Layer 111 audits the durable task
journal that surrounds those answers.

Project L's `l_chat_tasks` table is a state machine. A saved result can be
cryptographically valid while the surrounding task record is internally
inconsistent. Layer 111 checks that ledger without replaying or repairing work.

## Endpoint

`GET /cognition/durable-task-ledger-audit`

The scan is owner-scoped, oldest-first, paginated, read-only, and capped at
10,000 rows by default.

## Invariants checked

For each durable task the audit checks:

- stored request hash still matches the stored request object;
- embedded request ID remains bound to the row request ID;
- owner/input hash shapes are valid;
- timestamps are parseable and `updated_at >= created_at`;
- queued tasks do not already have a worker, lease or result;
- running tasks have a worker and a live lease;
- running tasks do not already have a result;
- ready/failed terminal tasks have matching terminal checkpoints and result
  objects;
- interrupted tasks do not carry a result or a still-live lease.

## Expired running leases

A running task whose lease is already expired is reported explicitly. The audit
does **not** claim or replay it. Existing queue semantics remain responsible for
transitioning expired running work to interrupted.

## Privacy

Findings use a 12-character SHA-256 request reference only. The response never
returns request payloads, answer text, raw request IDs, owner hashes, input
hashes, credentials or signing-key values.

## No automatic repair

Layer 111 changes nothing:

- no task replay;
- no lease changes;
- no database writes;
- no memory writes;
- no automatic repair.

Detected ledger issues are diagnostic evidence for a later explicit repair
decision.

## Claim boundary

A complete healthy audit means the scanned durable task rows satisfy Project L's
journal/state-machine invariants at audit time.

It does not establish factual correctness or answer quality, and an incomplete
or capped scan cannot certify the full ledger.
