# Layer 131 — saved-review ordering

Saved-answer review adds an Order selector with Newest first (default) and Needs attention first. Attention results move above other checked results, preserving newest-first order within each group. The order is based on the existing browser task list, not the displayed check timestamps.

Search and status filters continue to apply. Later batches join the selected order, and Refresh review retains the selection. Existing detail nodes move without being recreated, preserving expansion state. Ordering is local and never sends or repeats requests.

Validation covers stable ordering, search intersections, returning to newest-first, refresh persistence and older batches without duplicate entries. Phone visual testing remains outstanding.
