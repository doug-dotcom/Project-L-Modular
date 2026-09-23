# Layer 107 — Production Cryptographic Readiness Gate

Layers 104–106 made saved-answer provenance authenticated, rotatable and
auditable. Layer 107 makes that security posture part of deployment health.

Railway already checks `/health`. Layer 107 changes that health contract so a
verified Project L production container must prove its provenance-signing
keyring is operational before Railway can promote the release.

## Production checks

For the exact Project L production identity, the gate requires:

1. keyring mode is active;
2. an active signing key ID exists;
3. the active key secret is configured;
4. the active key ID is explicitly listed in the verification set;
5. the retained Layer 104 verification key is still available;
6. a synthetic answer-provenance object can be signed with the active key;
7. that signature verifies against the current keyring;
8. the produced key ID matches the configured active key ID.

The self-test uses synthetic hashes only. It does not read a saved answer,
prompt, memory record or user data.

## Railway health behavior

When the runtime identifies itself as the real Project L production deployment:

- all checks pass → `GET /health` returns HTTP 200;
- any cryptographic readiness check fails → `GET /health` returns HTTP 503.

Because Railway's service healthcheck path is already `/health`, a broken
production keyring now blocks rollout rather than becoming a nominally healthy
deployment.

Non-production/local runtimes remain observable but are not blocked by this
production gate.

## Operator endpoint

`GET /cognition/security-readiness`

returns the same privacy-safe readiness report behind the existing account
boundary.

The report may include non-secret key IDs and issue codes. It never returns:

- signing-key values;
- HMAC signatures;
- answer text;
- prompts;
- private memory.

## Rotation contract

Layer 107 currently requires the Layer 104 legacy verification key because
Layer 105 deliberately preserved historical Layer 104 signatures.

A future explicit migration may revise that requirement only after historical
dependency has been reviewed. The gate does not auto-retire any key.

## Claim boundary

A passing gate establishes that the running production keyring can create and
verify Project L answer-provenance signatures with the configured active key.

It does not establish factual correctness, answer quality, memory quality,
intelligence or human acceptance.
