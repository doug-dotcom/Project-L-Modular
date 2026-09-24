# Layer 135 — copy a saved question and answer together

Saved review offers Copy question and answer when the original question is non-blank and the ready answer passes delivery verification with non-blank answer text. The copied text labels the question and answer, preserves their wording and includes the same freshness warning shown in the review. The composer draft is unchanged.

The action uses the existing clipboard handler, including duplicate-click prevention, fixed fallback guidance and stale-review/account guards. It does not send a message or repeat a task.

Validation covers the production freshness formatter, exact multiline copying, draft preservation, unavailable/failed/empty/rejected answers, blank questions, clipboard failures and a late clipboard completion after closing the review. Phone visual testing remains outstanding.
