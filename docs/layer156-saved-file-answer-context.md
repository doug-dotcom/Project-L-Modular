# Layer 156 — Reopen saved file answers in their source context

Opening a saved file answer now confirms and reopens the original saved file and physical page before recovering the answer. The file selector, page preview and question are aligned with the saved request, so an old answer cannot appear beside an unrelated current file view.

The current view is preserved if the original file, requested page or saved-file list cannot be confirmed. Changing the page or account while that context is loading invalidates the old attempt. These checks do not resubmit the question. Older saved entries that predate stored file/page context remain recoverable, but the file preview is cleared rather than implying an unsupported source relationship.

Seven regression scenarios cover aligned recovery, missing originals, removed pages, malformed lists, page changes, account changes and legacy history. Existing file recovery and history suites remain part of full CI. Phone visual testing remains outstanding.
