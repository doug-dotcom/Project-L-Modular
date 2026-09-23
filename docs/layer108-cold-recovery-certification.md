# Layer 108 — Cold Saved-Answer Recovery Certification

Layer 106 can audit a bounded set of recent saved answers. Layer 108 adds a
single-answer **cold recovery certification** for an exact durable task.

The certification deliberately bypasses Project L's in-process result cache and
reads the persistent `l_chat_tasks` record directly.

## Endpoint

`GET /cognition/recovery-certification/{request_id}`

The endpoint is owner-scoped using the existing recovery-token identity. It
queries by:

- exact request ID;
- owner user ID;
- owner recovery-token hash;
- limit 1.

It performs no writes, task replay, model calls or memory updates.

## What it verifies

For the selected saved answer, the certificate applies the current recovery
stack:

1. delivery-receipt verification;
2. request/reply provenance binding;
3. release-provenance verification;
4. answer-authenticity/HMAC verification when required;
5. current signing-key/keyring verification;
6. protocol compatibility.

It then compares the answer's stored generating commit with the currently
running production commit.

## Result classes

A record may report:

- `certified_current_release`
- `certified_historical_release`
- `certified_provenance_compatibility`
- `legacy_readable_not_modernly_authenticated`
- `not_ready`
- `not_found`
- `failed_integrity`

A historical release is not treated as invalid merely because Project L has
since deployed newer code. If its persisted receipts and authenticity still
verify under the retained keyring, the answer remains certified.

Legacy answers may remain readable without being upgraded into a claim of modern
HMAC authentication.

## Privacy

The response never returns:

- saved answer text;
- prompt text;
- retrieved evidence;
- raw request IDs;
- signing-key values;
- HMAC signatures.

The request is represented only by a 12-character SHA-256 prefix.

## Cold-recovery meaning

"Cold" means the certification depends only on persistent storage plus the
currently running verification code/keyring. It does not trust an in-memory
result from the process that originally generated the answer.

This makes the endpoint useful after:

- Railway deploys;
- process restarts;
- code upgrades;
- signing-key rotations.

## Claim boundary

A successful certificate means the persistent saved answer can be recovered
today under Project L's current integrity/provenance/authenticity contracts.

It does **not** establish:

- factual correctness;
- answer quality;
- memory quality;
- intelligence;
- that an historical release was better or worse than the current release.
