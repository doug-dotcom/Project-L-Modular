# Layer 106 — Saved Answer Integrity Audit

Layer 106 turns the provenance/authenticity work from Layers 101–105 into a
practical production audit.

The new owner-scoped endpoint:

`GET /cognition/integrity-audit?limit=50`

reads recent saved chat-task results and verifies them without replaying the task,
calling a model, writing memory or changing any stored record.

## What the audit verifies

For each sampled saved answer it checks:

1. delivery integrity;
2. answer-provenance integrity;
3. recovery protocol compatibility;
4. HMAC authenticity when required;
5. release-commit binding;
6. signing-key ID usage.

The report returns aggregate counts for:

- delivery states;
- recovery/provenance states;
- protocol versions;
- release commits;
- signing-key IDs;
- issue codes.

Invalid records receive only a privacy-safe request reference made from the first
12 hex characters of SHA-256(request_id). Raw request IDs are not returned.

## Privacy boundary

The audit may read the stored answer internally because its exact text is required
to verify the answer hash. The response never returns:

- answer text;
- prompt text;
- retrieved evidence;
- raw request IDs;
- signing-key values;
- API/database credentials.

## Ownership and bounds

The endpoint uses the existing recovery-token owner identity used by the durable
task system and production baseline. Queries are filtered by both owner fields,
ordered newest-first and bounded to 1–100 tasks.

No schema change is required.

## Key rotation

The audit reports observed signing-key references so operators can understand
which key generations are represented in the bounded sample.

It deliberately does **not** say a key is safe to retire. Absence from a recent
sample is not proof that older saved answers no longer depend on that key.

## Claim boundary

Passing integrity/authenticity checks means the sampled stored payloads match
their delivery and provenance contracts.

It does not score factual correctness, answer quality, memory quality,
intelligence or human acceptance.
