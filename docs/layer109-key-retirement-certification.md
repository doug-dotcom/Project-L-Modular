# Layer 109 — Signing-Key Retirement Certification

**Current behaviour:** Layer 116 supersedes the zero-reference eligibility
described below. Owner-only scans now report `no_references_in_owner_scope`,
never retirement eligibility. Uncertain records block a clean assessment, and
the loader uses the bounded stable scan. See
[Layer 116](layer116-key-dependency-scope.md) for the current contract.

Layers 105–106 could show signing-key usage in recent or bounded samples, but
they deliberately could not prove that a historical key was unused across all
saved answers.

Layer 109 adds an owner-scoped, paginated dependency certification over durable
`l_chat_tasks` history.

## Endpoint

`GET /cognition/key-retirement-certification`

Optional bounds:

- `page_size`: 1–100, default 100
- `max_rows`: 1–10,000, default 10,000

The scan is read-only and uses the existing recovery-token owner identity.

## Conservative dependency counting

Layer 109 counts **raw stored signing-key references** before deciding whether a
record is valid.

This is intentional. A corrupted answer that still references an old key keeps
that key classified as in use. Invalidity is not treated as permission to retire
a dependency.

It recognises:

- current keyring key IDs;
- retained inactive key IDs;
- the Layer 104 legacy signing-key generation;
- unclassified signed references.

## Complete vs incomplete scans

A key with zero references is marked only:

`eligible_for_operator_review`

and only when:

1. the durable scan reached the natural end of the owner's task history;
2. the safety cap was not hit;
3. the key is not currently active.

If the scan is capped or incomplete, zero-reference keys remain:

`unknown_incomplete_scan`

The active key is always:

`active_do_not_retire`

A referenced inactive key is:

`in_use`

## No automatic retirement

Layer 109 never changes Railway variables, deletes a key, edits saved answers or
writes database state.

Even after a complete zero-reference result, an operator review is required
before any key configuration changes.

## Privacy

The report returns aggregate key IDs, dependency counts, verification states and
issue codes only.

It never returns:

- answer text;
- prompts;
- evidence;
- raw request IDs;
- signing-key values.

## Claim boundary

A complete scan with zero references supports the narrow statement that no
stored durable task in the scanned owner history references that key generation.

It does not prove answer quality, factual correctness, or that external backups
outside `l_chat_tasks` have no dependency on the key.
