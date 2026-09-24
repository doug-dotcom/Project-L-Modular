# Layer 119 — Explain saved-answer recovery findings

Check saved answers now separates recoverable results, unfinished tasks, failed
recovery checks and records that could not be assessed. The total includes
malformed rows, so damage cannot disappear from the displayed record count.
Task-record problems are shown separately with an explicit overlap note; they
are not added a second time to the recovery counts.

Partial scans clearly limit their counts to the records checked. Unfinished tasks
carry review-before-resending guidance. Recoverable failed-task messages are
explicitly distinguished from successful task completion. No task is replayed
or repaired by this display.

The browser validates bounded integer counts, reconciles both report totals,
and rejects contradictory ready, empty, pending or incomplete statuses. Fixed
copy and numeric counts remain the only displayed inputs. Existing timeout,
retry, account-change and privacy protections remain covered by the DOM tests.
Backend-to-browser regression cases use actual readiness reports, including
malformed rows, broken signatures, failed results and incomplete scans.

Live verification covers deployment identity, health, public asset delivery and
anonymous access rejection. Signed-in phone acceptance remains outstanding.
