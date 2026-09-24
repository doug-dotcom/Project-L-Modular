# Layer 125 — saved-answer focus

Use question now scrolls the focused message box into view without animation. An existing different draft still prevents replacement and scrolling. The question is never sent automatically.

Escape within the saved-answer review closes it and returns focus to the + button. Composition events and keys already handled by another control are respected. Closing invalidates pending retrieval, and an old panel cannot close a newer review. The visible Close review button uses the same behaviour.

Validation: regression coverage checks focus and scrolling only after successful question reuse, keyboard dismissal during an unresolved fetch, suppressed late results, and stale-panel isolation. Phone visual testing remains outstanding.
