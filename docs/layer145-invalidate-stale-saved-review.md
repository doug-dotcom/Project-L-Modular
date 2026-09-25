# Layer 145 — mark changed saved-answer reviews as out of date

An open Saved answers review now becomes out of date when a new task starts in this tab, or another tab changes the saved-task list or recovery token or clears browser storage. The notice explains what changed and directs the user to Refresh review. Already checked entries remain visible with their original check times.

Invalidation stops the current review pass, disables checking older tasks from that snapshot, and ignores late fetch or verification results. Refresh starts a new review from current browser data, retaining existing search, filter and expansion choices. Unrelated storage changes are ignored; closed reviews are not reopened by these events. This does not stop or repeat server tasks.

Validation covers new tasks, saved-list changes, recovery-token changes, storage clearing, unrelated storage, late fetch and verification results, refresh state preservation, and events after closing or resetting the account. Phone visual testing remains outstanding.
