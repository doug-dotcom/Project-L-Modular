# Layer 123 — Compact saved-answer navigation

Checked tasks now appear as native expandable details, initially closed, with a short plain-text question preview. Needs attention remains visible in the summary for flagged results. Opening one reveals the full question and its checked answer or notice. Search still covers checked display text even when the detail is closed.

Expand all and Collapse all affect checked entries and set the starting state for later batches. Clear filters restores all checked tasks and focuses the search field. Close review removes the section and invalidates outstanding retrieval through the existing reset guard; it does not stop or repeat server tasks. An old review's controls cannot affect its replacement.

No new requests or persistence operations are added by the navigation controls. Existing integrity, search, filtering, batch, stop and account regressions are retained. Phone visual testing remains outstanding.
