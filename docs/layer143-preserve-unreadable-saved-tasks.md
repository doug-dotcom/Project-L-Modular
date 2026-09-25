# Layer 143 — preserve unreadable saved-task data

Saved-task writes now require a successful browser-storage read and a JSON array. Invalid JSON, empty stored strings, non-array containers and read failures cannot silently become an empty history that overwrites existing data. A genuinely missing storage key still starts a new history normally.

Both recording a pending task and marking a delivered task complete use this check. If recording fails, the existing send guard keeps the draft unsent. If completion bookkeeping fails, the delivered answer remains visible and the saved data and pending pointer remain untouched. Read-only startup and review retain their tolerant behaviour. Damaged data is preserved, not repaired.

Validation covers malformed and empty JSON, null/object/scalar containers, denied reads, missing and valid histories, exact draft retention, no unwanted submission, and damage/read failures during answer delivery. Phone visual testing remains outstanding.

The combined release also aligns three remaining Shine-AI bridge test request headers with its updated test token. The bridge suite is now included in CI so authentication, owner/scope boundaries and bounded recall run on future releases. Production bridge behaviour is unchanged.
