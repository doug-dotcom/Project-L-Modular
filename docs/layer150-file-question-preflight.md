# Layer 150 — File-question preparation

File questions now prepare and save a valid recovery handle before clearing the displayed answer, setting the busy state or sending a request. Storage read/write failures, unreadable saved recovery details and request-ID generation failures leave the question, preview and answer in place. The Ask button remains usable and the status explains that this attempt was not sent, with guidance to check Saved file answers before trying again.

Matching questions reuse their existing valid request ID. Submission bodies are rebuilt from the selected document, page and question plus that ID, so extra properties in a saved marker are not forwarded. Unreadable markers are preserved rather than overwritten. No request or recovery poll starts after failed preparation. Resolving the underlying browser/storage problem permits an explicit later retry; this change does not automatically repair or discard saved markers.

Validation: 12 new scenarios cover storage failures, malformed JSON and marker shapes, missing/invalid IDs, ID generation failure, valid ID reuse, a changed question and explicit retry after the preparation problem is resolved. Existing recovery, account-isolation and file-timeout suites remain covered by full CI. Phone visual testing remains outstanding.
