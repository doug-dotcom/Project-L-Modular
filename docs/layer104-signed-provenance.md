# Layer 104 — Server-signed answer provenance

Layers 101–103 made production source identity and saved-answer provenance
tamper-evident with public hashes. Layer 104 adds **authenticity** using an
HMAC-SHA256 signature produced with a server-only Railway secret.

## Why this layer exists

A public SHA-256 receipt can detect accidental corruption and ordinary tampering,
but an actor who can rewrite stored data can also recompute public hashes.

For new production answers, Layer 104 signs the complete Layer 102
answer-provenance receipt with a secret available only to the Project L runtime.

The secret is stored in Railway as:

`L_ANSWER_PROVENANCE_SIGNING_KEY`

It is never included in chat payloads, logs, health output, provenance receipts or
GitHub.

## Protocol v2

New signed answers declare:

`answer_provenance_protocol: "2.0"`

Recovery requires:

1. the existing delivery receipt to validate;
2. Layer 102 answer provenance to validate against the exact recovered answer and
   bound runtime receipts;
3. a valid HMAC-SHA256 authenticity receipt for that exact answer-provenance
   object.

Changing the provenance and recomputing every public hash is insufficient because
the attacker cannot create a new valid HMAC without the server secret.

## Compatibility

- Layer 104 production answers use protocol v2 and require a valid signature.
- Layer 103 protocol-v1 answers remain readable and continue to receive their
  public-hash provenance checks.
- Layer 102 and genuine older answers retain their existing compatibility paths.

Verified production fails closed if the signing key is unavailable. Local or test
runtimes that do not identify as verified production may continue through the v1
compatibility path.

## Security boundary

The HMAC protects authenticity as long as the signing secret remains private.
Compromise of the Project L runtime secret itself is outside this guarantee.

The signature establishes that the provenance receipt was produced by a runtime
holding the Project L signing secret. It does **not** establish factual
correctness, answer quality, memory quality, or human acceptance.

Key rotation is intentionally separate from this layer so rotation can preserve
verification of historical signatures rather than silently invalidating them.
