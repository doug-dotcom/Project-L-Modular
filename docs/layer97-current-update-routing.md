# Layer 97 — current-day update routing

The labelled daily-update guard missed ordinary current-day narratives. Broad
family, recovery and project cues could therefore request historical retrieval
when the user had already supplied the material for a conversational response.

Controller 2.0 recognises substantive first-person prose opening with a current-day
anchor, plus morning/evening update labels. It uses the supplied message without
calling historical retrieval. Existing identity and conversation context remain
available; this is not a universal context-window limit. No stored record is removed
or rewritten and intake still runs.

Questions and request cues veto the shortcut. The new route additionally declines
continuity wording, short messages and ambiguous openings. Explicit investigation
keeps the existing focused, investigation and period-review budgets and evidence
gates. High-stakes reasoning and external-evidence requirements remain active.
The controller records self_contained_current_update separately from the original
self_contained_daily_update signal so saved receipts distinguish the routes.

Validation uses synthetic routing cases and the actual server chat path with a
fixture model, asserting no historical retrieval, preserved user-message writes,
brain intake and generation input. This does not establish live response quality
or production latency improvements. General adaptive context budgets remain future
work; this layer extends only the zero-historical-retrieval route.
