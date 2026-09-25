# Layer 153 — Preserve the open file when refreshing

Refreshing saved files now retains an available selected file, its current page, preview, draft question and displayed answer. The original is immutable, so retaining it avoids an unnecessary preview read and does not interrupt an answer already being recovered.

A file missing from the refreshed list clears the old selection, preview and answer, and resets page controls. A newly uploaded file still opens on page one. Malformed lists and read failures leave the current view intact. Newer refresh requests supersede older successes and failures; existing account/selection guards still apply.

Ten new scenarios cover preserved views, in-flight answer recovery, upload selection, concurrent refreshes, page changes, removed files, malformed lists and failures. Full CI and live-file checks accompany the release. Phone visual testing remains outstanding.
