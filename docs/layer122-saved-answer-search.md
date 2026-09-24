# Layer 122 — Search checked saved answers

Saved-answer reviews have a labelled search field and All checked tasks / Needs attention filter. Search matches task text and the answer or notice actually displayed, ignoring case and surrounding spaces. Both filters combine without network requests or task changes. A live visible count states the search scope; older tasks join it only after their batch is checked.

Needs attention includes unfinished and unavailable tasks, failed/interrupted results, verification failures and ready answers whose freshness is superseded or unavailable. It does not certify factual correctness for other answers. Unknown task statuses now display an unavailable notice instead of implying work is still running.

Each task and result stays together in one article. Search state carries through additional batches, and existing stop/account guards remain. Rejected answer text never reaches the search index. Four regression scenarios cover matching and clearing, combined filters, rejected-text exclusion and filtered older batches. Phone visual testing remains outstanding.
