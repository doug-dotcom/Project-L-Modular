# Layer 140 — preserve unsent picture prompts

The fallback picture sender now saves its pending request before displaying the picture or clearing the composer. If local preparation fails, it leaves the exact prompt and file selection intact, focuses the composer and explains that the picture was not uploaded. No upload begins on that path.

A later retry follows the existing image-submission flow. The account evidence uploader remains separate. This change does not repair malformed local data; a partially successful local write can leave an unsubmitted request handle for later checking.

Validation covers task and pending-pointer write failures, malformed saved-task data, exact prompt and file preservation, no preview or network upload on failure, and a successful subsequent retry. Phone visual testing remains outstanding.
