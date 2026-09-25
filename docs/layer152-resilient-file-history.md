# Layer 152 — Resilient saved file-answer history

History now builds its list before replacing the displayed entries. It skips malformed entries individually, reports their count and keeps valid questions usable. A genuinely empty response has a distinct empty-state message. An unreadable response or connection failure preserves the displayed list and offers retry guidance.

A newer history request supersedes earlier requests, including their errors. A late history result cannot overwrite the status of an answer check started after it. Account changes still invalidate pending history reads. These history operations do not submit questions or modify saved tasks.

Nine new scenarios cover mixed and entirely malformed entries, empty history, malformed response envelopes, read failures, out-of-order success/error results, and answer-status preservation. Existing file recovery, timeout and account-isolation tests remain included in full CI. Phone visual testing remains outstanding.
