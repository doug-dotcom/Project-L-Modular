# Layer 136 — coordinate saved-answer copying

Saved review permits one clipboard write at a time across its copy controls. While a write is pending, its button reads Copying… and other copy controls are disabled, including controls added by older batches or a refreshed review. This prevents competing writes from finishing out of order.

Completion or failure restores copying. The existing active-review checks prevent a late operation from posting a status into a replacement review. Closing a review discards its control references while retaining the pending-write guard until the browser settles that operation. Draft and task behaviour remain unchanged.

Validation covers competing buttons across entries, older batches, refresh during a pending write, successful completion and rejection, restored labels and a subsequent copy. Phone visual testing remains outstanding.
