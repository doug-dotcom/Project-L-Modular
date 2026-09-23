# Layer 103 — Provenance-verified saved-answer recovery

Layer 102 binds a completed answer to its generating runtime release. Layer 103
makes that provenance part of the save and recovery contract instead of checking
it only when the answer is first created.

## New protocol marker

New Layer 103 chat answers include:

`answer_provenance_protocol: "1.0"`

The marker is inserted **before** the existing delivery payload is sealed, so it
is covered by delivery integrity.

For a marked answer:

- answer provenance must be present;
- the receipt must validate against the exact recovered reply and request ID;
- release provenance must still validate;
- model, context-budget and persistence receipt hashes must still match.

A marked answer with missing or invalid provenance is withheld on recovery.

## Rollout compatibility

Layer 103 does not break older saved answers:

- Layer 102 answers have provenance but no Layer 103 protocol marker; their
  provenance is verified when present.
- Genuine pre-provenance answers remain readable under the existing legacy
  compatibility path.
- A present-but-malformed provenance field is never treated as legacy.

## Recovery surfaces

Verification now runs in both recovery stores:

1. durable Supabase task results;
2. the short-lived in-process legacy chat-result cache.

The durable store also rechecks recovery provenance immediately before writing a
finished result.

## Security boundary

The protocol prevents an answer that is **marked as provenance-required** from
silently becoming a legacy answer merely because its provenance field is missing
or corrupt.

These receipts use public hashes for integrity and consistency; they are not
secret-key digital signatures. Someone with authority to rewrite every stored
field and recompute every public hash is outside the guarantee of this layer.

## Claim boundary

A passing recovery check establishes that the returned saved answer still matches
its stored delivery and provenance contracts.

It does not establish factual correctness, answer quality, memory quality, or
human acceptance.
