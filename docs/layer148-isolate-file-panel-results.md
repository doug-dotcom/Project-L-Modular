# Layer 148 — isolate late file-panel results

File-answer checks now belong to the current answer view and account session. Choosing another file or page, starting a new question, or opening another saved answer invalidates the earlier check. Late replies cannot replace the new view, trigger speech or clear its pending marker. A file-list refresh that arrives after a new file selection cannot overwrite that selection.

Locking the account or signing in again clears the file panel and invalidates outstanding work. Late file lists, previews, history, upload completions and original-file downloads are ignored across that boundary. Earlier cleanup handlers cannot unlock a newer session's active question. These guards affect browser presentation; they do not cancel or repeat server tasks or delete pending recovery data.

Validation covers out-of-order answers, file/page changes, delayed acknowledgements, account lock and re-sign-in, old completion handlers, late lists/previews/history/uploads/downloads, stale selection errors and list refreshes. Existing bounded-recovery tests remain active. Phone visual testing remains outstanding.
