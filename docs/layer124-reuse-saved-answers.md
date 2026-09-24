# Layer 124 — Reuse checked saved answers

Expanded saved entries offer Use question, which fills an empty message box and focuses it for review. It never sends a message and preserves a different existing draft. Copy answer is offered only for ready answers that passed the existing delivery verification. It copies the displayed answer including freshness warnings, with an explicit fallback notice when clipboard access fails.

Actions require the original review to remain active and the account to remain ready. Completed entries remain usable after stopping further retrieval. Failed, interrupted, unavailable and verification-rejected results do not receive a Copy answer control. No new model call or server write is added. Clipboard writes start only on the user's click; closing a review cannot undo an already initiated clipboard operation.

Regression coverage exercises preserving drafts, explicit reuse without sending, copying freshness warnings, clipboard failure, and rejected-result exclusion. Phone visual testing remains outstanding.
