# Layer 102 — Answer-level release provenance

Layer 101 proves which source identity the running container reports. Layer 102
binds that release identity to each completed answer so saved responses remain
auditable after Project L moves to later commits.

## Answer provenance receipt

Immediately after assistant persistence, Project L creates a self-hashed receipt
binding:

- exact request ID;
- SHA-256 of the exact final reply;
- release layer;
- exact Railway/Git commit SHA;
- Layer 101 release-provenance receipt hash;
- response-model receipt hash;
- adaptive context-budget receipt hash;
- assistant-persistence receipt hash.

The receipt stores hashes, not answer text, prompts, evidence, credentials or
model payloads.

## Verification

Before the final chat payload is sealed, Project L independently verifies the
answer-provenance receipt against the live objects that created it. A mismatch in
the reply, request, release commit, model receipt, context budget or persistence
receipt makes the receipt invalid.

A forged receipt cannot become valid merely by recomputing its public self-hash:
verification also checks it against the full Layer 101 release-provenance receipt.

If this binding fails during a live answer, Project L withholds the answer rather
than saving ambiguous provenance.

## Historical production baseline

The read-only production baseline now reports:

- answer-provenance states;
- counts of verified saved answers by exact release commit.

This permits operational comparison of release cohorts without replaying tasks or
exposing private answer text.

A commit cohort is not a quality score and does not establish causal improvement.

## Claim boundary

A verified Layer 102 receipt establishes that the saved answer is cryptographically
bound to the reported runtime release identity and associated runtime receipts.

It does not establish factual correctness, intelligence, memory quality, or human
acceptance.
