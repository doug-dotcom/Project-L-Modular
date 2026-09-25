# Layer 149 — Bounded file requests

File lists, previews and saved-answer history now stop waiting after 15 seconds. Original downloads allow 30 seconds; uploads allow 60 seconds. The deadline covers both the request and its response body, even if the transport ignores cancellation.

A stalled upload releases the shared busy state and tells the user that saving may still finish. The user is directed to refresh saved files before uploading again. There is no automatic repeat submission. Timing out does not prove that the server cancelled an upload.

Late results cannot update the interface after the deadline. Existing account and selection guards remain in place. Timers are cleared after settlement; server validation messages are preserved.

Validation: 13 new virtual-clock scenarios cover stalled transports and bodies across all five operations, account locking, upload validation, no automatic repeat upload, late-result suppression, and an explicit subsequent upload. Existing file recovery and account-isolation suites also pass. Full CI and live deployment checks are recorded in the release PR. Phone visual testing remains outstanding.
