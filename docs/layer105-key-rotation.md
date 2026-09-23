# Layer 105 — Safe signing-key rotation

Layer 104 introduced server-secret HMAC authentication for saved-answer
provenance. A single permanent signing key would eventually become an operational
risk: replacing it would make historical signatures unverifiable.

Layer 105 adds a bounded keyring and performs the first planned rotation.

## Key model

Layer 104's original secret remains in:

`L_ANSWER_PROVENANCE_SIGNING_KEY`

It is retained **only to verify historical Layer 104 signatures**.

New Layer 105 signatures use a non-secret key identifier:

`k2-2026-09`

with Railway configuration:

- `L_ANSWER_PROVENANCE_ACTIVE_KEY_ID`
- `L_ANSWER_PROVENANCE_VERIFY_KEY_IDS`
- `L_ANSWER_PROVENANCE_SIGNING_KEY_K2_2026_09`

Only the key ID is written into new authenticity receipts. Secret key values
never enter payloads, health output, logs, tests, GitHub or production-baseline
reports.

## Rotation procedure

A safe future rotation is:

1. add a new secret under a new key-specific environment variable;
2. add its key ID to the verification list;
3. change the active key ID so new answers use the new key;
4. keep the previous key ID in the verification list while historical answers
   still need to validate;
5. use the production baseline's signing-key counts to understand retained usage;
6. retire an old key ID only as an explicit operational decision.

Simply removing a key ID from the allowed verification list makes signatures
under that ID fail verification, even if the secret value still exists.

## Compatibility

Layer 105 verifies both:

- Layer 104 legacy signatures with no key ID using the retained Layer 104 secret;
- Layer 105 keyring signatures using their explicit retained key ID.

Layer 103 protocol-v1 and older compatibility paths remain unchanged.

## Production baseline

The read-only production baseline now includes verified
`answer_authenticity_keys` counts per cohort. This supports key-rotation audits
without exposing answer text or secret material.

These counts are operational metadata, not answer-quality scores.

## Security boundary

Key IDs are public metadata; key values remain server secrets. HMAC authenticity
depends on those secrets remaining private.

Key rotation reduces long-term exposure and preserves historical verification. It
does not establish factual correctness, intelligence, memory quality or human
acceptance.
