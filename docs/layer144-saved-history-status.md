# Layer 144 — explain unreadable saved history

Saved answers now distinguishes a genuinely empty history from browser storage that could not be read or parsed. An accessible notice explains that the unreadable data has been left unchanged, and offers Refresh review after checking storage access. The panel no longer suggests sending a first message when existing history is unreadable.

When only individual entries lack usable request identifiers, review reports the number skipped and continues checking valid entries. If every entry is incomplete, it explicitly says no tasks were checked. Refresh reads the history again and clears the notice when the issue is resolved. This layer does not repair or delete saved data.

Validation covers invalid JSON, non-array history, denied reads, empty and missing history, mixed entries, entirely incomplete entries, refresh recovery and a later read failure. Existing review and storage-preservation suites remain active. Phone visual testing remains outstanding.
