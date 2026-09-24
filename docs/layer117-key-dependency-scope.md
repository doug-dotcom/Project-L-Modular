# Layer 117 — Conservative signing-key dependency evidence

The key-dependency endpoint inspects one recovery-token owner's history, while
signing keys are shared by the service. A complete owner scan cannot establish
that another owner, another browser or an external backup has no dependency.

Layer 117 preserves the read-only endpoint and replaces the earlier
`eligible_for_operator_review` label with `no_references_in_owner_scope`.
Every candidate now has `retirement_eligible: false`. A separate global
dependency check is explicitly required; this endpoint cannot authorise it.

## Conservative handling of damaged records

- Raw references to configured keys are counted before checking the request ID.
  A malformed ID cannot erase a visible dependency.
- A legacy receipt always retains its legacy dependency, including when a
  conflicting extra key ID is present. Both visible configured references remain
  protected in that case.
- Unknown key labels and malformed authenticity metadata use the fixed
  `unclassified_signed_reference` bucket, without returning arbitrary labels.
- Malformed rows, missing terminal results, unverifiable answers and verifier
  exceptions contribute to `uncertain_rows`. Each row is counted once there.
- Verifier exceptions do not stop the scan or expose exception details.
- A legacy key still used for signing is protected even with zero saved answers.

Known references stay `in_use` despite uncertainty or an incomplete scan. The
active key stays `active_do_not_retire`. With zero references, an incomplete scan
returns `unknown_incomplete_scan`; a finished scan with uncertainty returns
`unknown_unassessed_records`. Only a finished assessment with no uncertain rows
can return `no_references_in_owner_scope`.

`scan_complete` describes query completion. `dependency_assessment_complete`
additionally requires zero uncertain rows. `malformed_rows_ignored` remains only
as a compatibility count alias; malformed rows now block the clean assessment.
Raw reference counts can exceed `answers_observed` because visible references
are retained even from rows with invalid IDs.

## Stable scan and boundaries

The loader reuses the Layer 115 shared scan: owner filters on every query,
creation-time and UUID continuation, fixed scan-start boundary, caps, and
explicit failure for malformed or non-advancing continuation keys.

This is not a transactional snapshot. Other owners, later tasks and external
backups are outside scope; concurrent changes can still affect findings. The
report neither changes keys nor replays tasks, repairs records, calls a model
or writes memory/database state. No migration is required.

## Verification

Tests cover owner/global scope, malformed IDs retaining key references,
unknown receipt labels, terminal missing results, invalid signatures, legacy
signing protection, conflicting receipts, exceptions, caps and valid legacy
readability. A real Supabase-client query against a mock HTTP service verifies
that deletion of an earlier row between pages cannot hide a later key reference.
