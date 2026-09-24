# Layer 138 — preserve drafts when local request storage fails

Chat submission now creates the recovery token and saves the pending request before clearing the composer or displaying a sent user message. If that preparation fails, the exact draft remains in the composer, focus returns to it and a fixed message explains that the request has not been sent. No chat submission or answer recovery is attempted on this path.

A later user retry follows the normal submission flow after storage is available. An earlier successful local write can remain if a subsequent local write fails; it does not represent a submitted server task. This change does not repair malformed saved data or alter image submission.

Validation covers recovery-token, saved-task and pending-pointer write failures, malformed saved-task data, exact draft preservation and a successful subsequent retry without duplicate network submission. Phone visual testing remains outstanding.
