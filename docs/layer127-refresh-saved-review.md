# Layer 127 — refresh saved-answer review

Refresh review starts a new check of the newest 20 saved tasks, using the current browser task list. Search, status filter and Expand all preference carry over. Older batches can be loaded again. Counts and answer actions are rebuilt from newly checked results.

Refresh is disabled during a batch. Stop checking enables it immediately, while late responses from the previous review remain ignored. Closing or changing accounts invalidates old controls. Refresh only retrieves existing task results; it never sends a task again.

Validation covers running-to-ready updates, new tasks, retained view settings, duplicate refresh prevention, stopped pending requests, late responses and account invalidation. Phone visual testing remains outstanding.
