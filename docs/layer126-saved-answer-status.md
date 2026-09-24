# Layer 126 — saved task status filters

Saved answers adds Answers available and Still working to the Show filter. Available means a non-empty, delivery-accepted ready answer can be copied. Queued and running tasks appear under Still working. Needs attention continues to include unfinished, unavailable, rejected and freshness-warning results.

Counts cover all checked entries, independently of the search and selected filter. Categories can overlap: a stale answer can be available and need attention. The UI explicitly labels this overlap and states that status reflects the last check. Older batches update the same counts and preserve the selected filter. Filtering does not poll, send or repeat tasks.

Validation covers mixed terminal and pending statuses, rejected delivery, fetch failures, search intersections, overlapping categories and later batches. Phone visual testing remains outstanding.
