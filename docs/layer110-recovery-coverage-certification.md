# Layer 110 — Durable Recovery Coverage Certification

Layer 108 can cold-certify one exact saved answer. Layer 110 extends that
question across an owner's durable saved-answer history:

**Can the current Project L release recover every durable answer it should be
able to recover, without replaying any task?**

## Endpoint

`GET /cognition/recovery-coverage-certification`

Optional bounds:

- `page_size`: 1–100, default 100
- `max_rows`: 1–10,000, default 10,000

The scan is owner-scoped, oldest-first, read-only and bypasses the in-process
result cache.

## What is measured

Each durable row is passed through Layer 108's cold recovery certificate using
one frozen view of the current production release.

The aggregate report distinguishes:

- modern authenticated current-release answers;
- modern authenticated historical-release answers;
- provenance-compatible older answers;
- readable legacy answers;
- incomplete tasks;
- failed recovery/integrity records.

Only hashed 12-character request references are returned for failures.

## Coverage claims

A complete uncapped scan may report:

- `all_ready_answers_recoverable: true` when every ready durable answer
  certifies under the current recovery stack;
- `all_observed_tasks_certified: true` only when every observed task is itself
  certified, including no incomplete tasks.

A capped or interrupted scan never makes a full-history coverage claim.

Legacy readability is counted separately and is never relabelled as modern
HMAC authentication.

## No replay or mutation

Layer 110 performs:

- no model calls;
- no task replay;
- no memory writes;
- no database writes;
- no cache-based recovery.

It verifies what is already stored.

## Privacy

The report never returns answer text, prompts, evidence, raw request IDs,
signing-key values or HMAC signatures.

## Claim boundary

Recovery coverage means durable records can be verified and reconstructed under
the current Project L recovery contracts.

It does not establish factual correctness, answer quality, memory quality or
that historical releases were better or worse than the current release.
