# Layer 115 — Combined recovery readiness

This release builds on the saved-answer protections merged as Layer 114 in
PR #85. Layer 113's stable scan is retained and shared with recovery coverage.

Task-ledger validity and saved-answer integrity were previously reported by
separate scans. Neither alone establishes that an observed task has a consistent
journal and a recoverable answer. Layer 114 fixed missing terminal results and
unassessed records being excluded from recovery failures. This layer applies
those protections alongside the ledger checks in one report.

## Behaviour

`GET /cognition/recovery-readiness` performs one owner-scoped, read-only scan.
The ledger and saved-answer checks inspect the same materialised rows. It
returns their separate findings with one combined outcome:

| Status | Meaning |
| --- | --- |
| `ready` | All observed task records are consistent and all their saved results are recoverable. |
| `ready_with_legacy` | Those checks pass, but some answers have legacy readability rather than modern authentication. |
| `pending_tasks` | Consistent unfinished or interrupted tasks remain. |
| `needs_attention` | A journal, saved result or malformed record prevents readiness. |
| `incomplete_scan` | The scan stopped, reached a cap or could not continue reliably. |
| `no_tasks` | No tasks were observed; readiness has not been demonstrated. |

`recovery_ready` is true only for `ready` and `ready_with_legacy`. A separate
check reports whether every observed answer has modern HMAC authentication.
Recoverable failed-task results do not imply successful task execution.

The existing recovery-coverage endpoint now uses Layer 113's stable timestamp
and UUID cursor, fixed scan-start boundary and invalid-page guards. Layer 114's
rules for missing results, malformed rows and bounded findings remain in force.

Cold certification also rejects results attached to unfinished tasks and uses
fixed labels for unknown statuses or unsupported provenance markers. Malformed
protocol JSON fails verification safely. A per-record verifier exception is
counted as unassessed, prevents readiness and does not expose exception text.

## Boundaries

Existing account authentication and recovery-token owner filters apply. The
response contains aggregate counts and hashed request references, never raw
requests, answers, IDs, owner tokens or signing keys. No task is replayed or
repaired. No model is called, no in-process answer cache is used, and no database
or memory writes or schema changes are introduced.

The reports share observations, not a transactional snapshot. Tasks created
after the recorded boundary need a new scan. Concurrent deletions, backdated
inserts, ordering-key edits and state changes can affect coverage or findings.
Integrity and recoverability do not establish answer quality or factual accuracy.

## Verification

Regression cases cover valid answers with damaged journals, valid journals with
tampered answers, missing terminal results, malformed records, unfinished tasks,
legacy readability, missing verification keys, caps, empty histories, bounded
findings and failed-task semantics. Real Supabase-client requests with a mock
HTTP transport verify one shared scan, owner filters, cursor continuation,
fixed boundaries and output privacy. Route tests cover account authentication,
owner-token validation and redacted database failures. Layers 110–114 retain
their regression coverage, including records changing between pages.
