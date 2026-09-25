# Layer 151 — Validate recovered file answers

A ready response must contain a non-empty text answer before the file panel reports recovery, speaks the answer or clears its pending recovery handle. Supplied source details must have a filename, positive integer page and an optional array of text quotes. A ready response carrying an error is not treated as a recovered answer.

Unreadable results produce a fixed explanation and retain the recovery handle, with guidance to check Saved file answers again. They do not trigger another submission or speak malformed content. Existing failed/interrupted responses without a payload retain their explicit incomplete-question fallback.

Twelve regression scenarios cover missing and malformed replies, malformed source fields, ready/error contradictions, valid cited answers and terminal failure handling. Full CI and live verification accompany the release. Phone visual testing remains outstanding.
