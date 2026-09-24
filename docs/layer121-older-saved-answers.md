# Layer 121 — Older saved answers

Saved-answer reviews now retain a snapshot of up to 100 browser-held task handles, newest first. The initial check retrieves 20. Check older tasks retrieves the next batch on demand, without repeating displayed entries or changing the review scope when new handles appear. The progress line counts checked handles against this snapshot, not against the full server history.

Stopping or reaching the existing per-batch two-minute network budget leaves the next unchecked handle available through Continue checking. Each batch has its own response generation guard: a late response from a stopped batch cannot render or settle a task once continuation starts. Account changes still remove and invalidate the review. Exhausted reviews disable the older-task control.

No tasks are replayed and no new server endpoint or database write is introduced. Failed lookups count as checked entries and retain their individual notices; reopening Saved answers starts a fresh review if a retry is needed. Five regression scenarios cover complete pagination, snapshot stability, the 100-handle bound, account changes between batches and continuation while an old fetch remains unresolved.
