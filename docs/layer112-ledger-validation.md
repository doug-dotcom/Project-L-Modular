# Layer 112 — Reliable ledger diagnostics

Layer 111 introduced the read-only durable task audit. Its parser could compare
timezone-free dates against UTC dates and abort the entire report. It also
accepted 64-character non-hex hashes and requests with missing embedded IDs,
and echoed unknown status values into its diagnostic response.

Layer 112 hardens the existing `/cognition/durable-task-ledger-audit` endpoint:

- Missing, malformed and timezone-free timestamps become issue codes. Valid
  timezone offsets are normalised to UTC before comparison.
- A malformed but present lease is distinguished from an absent lease.
- Request and worker IDs must parse as UUIDs; the embedded request ID is required
  and must identify the same UUID as the row. Hashes must be SHA-256 hex strings.
- Queued checkpoints must still be `queued`.
- Unknown status values become the fixed label `invalid`; private or corrupt
  content cannot be echoed through status findings or counter keys.
- Pagination orders by both creation time and request ID to break timestamp ties.
- Findings remain bounded to 50 while every row contributes to issue counts.
  `findings_omitted` reports invalid task rows beyond that display limit;
  non-object rows continue to have their separate `malformed_rows` count.

The audit keeps its existing token-owner scope and performs no writes, task
replays, lease changes or automatic repair. Existing queue lease semantics are
preserved, including a running lease being live at exact expiry equality.

Validation covers malformed records, ID binding, timezone offsets, privacy,
finding limits, the server endpoint, and a query exercised through the actual
Supabase/PostgREST client with a mock HTTP transport.

This remains a diagnostic scan, not a transactional snapshot. Ordering resolves
timestamp ties but concurrent deletions or state changes can still affect an
offset-paginated scan. It does not certify answer quality or factual correctness.
