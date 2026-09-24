# Layer 113 — Stable durable ledger scans

The task audit previously used offset pagination. Deleting a task that had
already been read could shift the next page and silently skip another task.
An insertion before the current page could cause a task to be counted twice.

The existing `GET /cognition/durable-task-ledger-audit` endpoint now continues
after the last `(created_at, request_id)` pair. Each page retains both owner
filters, ascending timestamp/UUID ordering, and the existing bounded page size.
No offset is used. Timestamp ties are resolved by UUID and timezone offsets
are normalised before constructing the continuation filter.

Every page applies the same `created_at <= scan_started_at` boundary. The
response records that boundary and limits its coverage claim to that scope.
The boundary uses the application server's UTC clock; a task timestamped beyond
that clock is excluded until a subsequent audit.

Malformed keys, repeated or unordered keys, oversized pages and rows beyond
the boundary stop the scan with a fixed, privacy-safe error code. They cannot
produce a complete or verified result. A malformed key's row diagnostics are
preserved; repeated rows are not counted again. `rows_read` counts records
received from the database, so it can exceed the number audited if a page is
rejected. A scan reaching `max_rows` remains conservatively capped, including
when the cap happens to equal the exact table size.

Continuation filters contain only parsed UTC timestamps and canonical UUIDs.
The response does not expose those UUIDs, request content, answers, owner
tokens or hashes. Existing authentication and owner scope remain in place.
All database requests are reads; there are no migrations, queue changes,
replays, automatic repairs, or memory writes.

## Verification

The Layer 113 suite exercises the pinned Supabase/PostgREST client with a mock
HTTP service, including deletion and insertion between pages, new tasks after
the scan boundary, equal timestamps, offset timezones, caps, invalid cursors,
broken pages, privacy, HTTP authentication and database failures. Existing
ledger tests continue to cover state-machine and malformed-record findings.

## Limitations

This is a bounded diagnostic scan, **not a transactional snapshot**. Deleting
an unread task, inserting backdated tasks behind the cursor, changing ordering
keys or changing task state during the scan can still affect coverage or
findings. A complete result means the bounded cursor traversal finished; it
does not prove the ledger existed in one consistent state at a single instant.
It does not score answer quality or factual correctness. These limits are
included in the API report.
