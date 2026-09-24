# Layer 139 — keep delivered answers visible

Updating local pending-request records is now best-effort: a failed storage write or removal no longer interrupts presentation of an answer already delivered. This shared cleanup path is used by live chat, recovered answers, saved review and image responses. It returns whether local cleanup completed, without exposing raw storage errors.

Existing task handles remain available if cleanup fails. A later visit may check the same task again; it does not submit that task again. Normal cleanup still marks matching tasks complete and removes only the matching pending pointer.

Validation covers task-write and pointer-removal failures, an answer recovered after an uncertain acknowledgement, later successful cleanup, unchanged single-submission behaviour and a saved-review answer remaining available to copy. Phone visual testing remains outstanding.
