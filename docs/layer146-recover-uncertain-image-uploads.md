# Layer 146 — recover uncertain fallback picture uploads

The fallback picture-upload path now uses the same bounded request helper as chat. It prepares its recovery token before uploading, waits at most 15 seconds for the upload acknowledgement/body, then checks the existing request ID in one bounded recovery window. A lost acknowledgement does not cause another upload.

If no answer is recovered, the pending request details remain available and the user is directed to Saved answers before uploading again. Only a delivered reply or explicit unsupported-file, invalid-size or invalid-ID rejection completes local pending bookkeeping. Rejection copy is fixed; network and server exception details are not shown. A late acknowledgement cannot add a second reply.

This changes the fallback `/image/start` flow used when the account file-upload handler is unavailable. The normal account file workflow is unchanged. Legacy image results retain their existing server-cache lifetime; this layer does not make those image results durable.

Validation covers successful recovery, dropped acknowledgements, stalled bodies, late acknowledgements, exhausted recovery without a second wait, explicit rejection statuses, cleanup write failure, and recovery-token storage failure before upload. Phone visual testing remains outstanding.
