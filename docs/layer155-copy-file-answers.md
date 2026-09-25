# Layer 155 — Copy file answers with source details

A Copy answer button now copies the displayed file answer, including its source filename, physical page, quotes and any image-interpretation warning. It is enabled only while there is a readable displayed answer in a ready account. Copying does not resubmit a question, change recovery status or trigger speech.

Clipboard feedback has its own polite status region. Missing clipboard support or a failed write offers manual-copy guidance without exposing the underlying error. Concurrent copy requests are prevented. Changing the file/page, starting a new answer or changing accounts clears the old copy feedback, and a late clipboard result cannot attach feedback to a newer view. A refresh that preserves the answer also preserves copying.

Eleven regression scenarios cover plain and cited answers, image warnings, failures, unavailable clipboard access, repeated taps, view/account changes, unreadable answers and refresh. Full CI and live-file checks accompany release. Phone visual testing remains outstanding.
