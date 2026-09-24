# Layer 118 — Recovery check follow-up

Recovery cards show the local check-start date and time and describe their point-in-time scope. Check again runs a fresh check; Open saved answers uses the existing retrieval control; Dismiss removes the card and returns focus to the + menu control. Buttons wrap and have a 44-pixel minimum height.

Starting a new chat or image task invalidates both completed and in-flight results. Changes to saved tasks or the recovery link in another tab also invalidate the card. Stale cards remove previous totals and success copy, without moving keyboard focus. Dismissed or superseded requests cannot restore old results. No check runs automatically.

These client events cannot observe every server-side change; the timestamp and manual refresh remain necessary. Existing account guards, timeout, privacy and GET-only behaviour remain in place.

Six new regression scenarios exercise actions, dates, task and cross-tab invalidation, unrelated storage changes, and late responses after invalidation or dismissal.
