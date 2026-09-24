# Layer 120 — Saved-answer review progress

Saved answers now opens one replaceable review section, checking the newest 20 browser-linked task handles first. A live progress line distinguishes tasks checked from tasks completed, including empty, finished, stopped and time-limited reviews.

Stop checking prevents further retrieval, display and pending-handle settlement from that review. It does not cancel server tasks or repeat them; an outstanding GET may still finish within the existing request timeout. Reopening starts a fresh review. Late responses from a stopped or older review cannot change the current one. Account locking or changing removes the review and invalidates outstanding work.

Existing delivery-integrity verification, freshness notices, per-answer failure isolation and the two-minute total network budget are retained. Regression fixtures now support the review DOM and assert newest-first ordering while preserving integrity and timeout checks. Eight new scenarios cover progress, empty/locked states, partial failures, stopping during fetch or verification, account changes and overlapping old/new reviews.
