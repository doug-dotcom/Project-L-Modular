# Layer 133 — copy saved questions

Saved review offers Copy question for non-blank original questions, including when the associated answer is unavailable or rejected. It preserves the exact question text and leaves the composer draft unchanged. Copy answer retains its delivery and freshness rules.

Both actions use a shared clipboard handler with duplicate-click protection, fixed fallback guidance and active-review/account checks. A clipboard operation already started cannot be undone, but its late completion cannot update a closed or replaced review. Copying never sends or repeats a task.

Validation covers exact multiline text, draft preservation, clipboard rejection, duplicate clicks, account invalidation and blank questions. Phone visual testing remains outstanding.
