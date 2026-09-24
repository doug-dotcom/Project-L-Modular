# Layer 130 — saved-result reasons

Collapsed saved-result headings now state the reason for attention: Still working, Task stopped, Facts changed, Freshness unchecked, Verification failed, Answer unavailable, Status unavailable or Check unavailable. Accepted ready replies without a warning retain Saved answer. Labels are fixed UI text, not upstream error strings.

Empty or whitespace-only replies are labelled No answer text, excluded from Answers available and Copy answer, and included in Needs attention. A freshness warning alone cannot make an empty answer available. Existing search, review timestamps and per-result text remain available.

Validation covers each status label and empty, whitespace-only and empty stale replies. Phone visual testing remains outstanding.
