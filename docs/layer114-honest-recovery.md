# Layer 114 — Honest saved-answer recovery results

Layer 114 closes false-success paths in saved-answer recovery certification.
A completed database scan is no longer treated as a complete assessment when
some records could not be assessed.

## Behaviour

- Ready or failed terminal tasks with missing/malformed results are recovery
  failures, rather than incomplete tasks that could be excluded from failures.
- Queued, running and interrupted tasks with no result remain incomplete.
  A result on one of these nonterminal states fails task-state certification.
- Unknown task statuses fail certification and use a fixed diagnostic label;
  arbitrary stored status content is never returned by the cold certificate.
- Malformed records and verifier exceptions block both aggregate success flags.
  The rest of the read-only scan continues. Exceptions are represented by a fixed
  issue code without exception messages or raw request data.
- Malformed JSON provenance protocol markers fail verification without raising
  an unhashable-type exception. This also protects actual saved-answer recovery.
  Cold certificates report unsupported markers using a fixed label rather than
  echoing their content.
- Coverage pagination breaks creation-time ties with request ID ordering.

## Report contract

`scan_complete` means the bounded query finished. `coverage.assessment_complete`
additionally requires zero unassessed records. `unassessed_rows` is the sum of
`malformed_rows` and `verification_error_rows`.

`rows_observed` counts every returned record. `answers_observed` counts records
with a valid request ID, including those whose verifier raised an exception.
`failed_recovery_records` counts assessed recovery/state failures;
`failed_ready_answers` is the subset explicitly marked ready in the database.

A finished scan with unassessed rows reports `complete_with_unassessed_records`
and `claims.durable_recovery_coverage: unverified`. A capped or unfinished scan
continues to report `incomplete_scan`. Neither permits full recovery claims.

The old `malformed_rows_ignored` field remains as a compatibility alias for the
malformed count. Its name must not be interpreted as permission to ignore those
records when evaluating coverage.

Findings stay bounded to 50 with `failure_findings_omitted`; counts include all
findings. References are hashed, and answer text is not included.

## Boundaries and validation

No task replay, automatic repair, model call, memory write or database migration
is introduced. Recovery protocols and valid legacy compatibility stay intact.
Certification still does not score factual correctness or answer quality, and
offset pagination is not a transactional snapshot.

Regression tests cover terminal and nonterminal states, malformed-only and mixed
histories, verifier exceptions, actual `TaskStore.get` protocol handling,
bounded findings, the HTTP handler, and the real Supabase/PostgREST client with
a mock transport verifying GET-only owner filters and stable ordering.
