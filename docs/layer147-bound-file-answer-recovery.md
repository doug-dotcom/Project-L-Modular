# Layer 147 — bound account file-answer recovery

Account file questions now bound their submission acknowledgement to 15 seconds and their recovery window to two minutes, including stalled network and response-body reads. A lost acknowledgement leads to checks of the same request ID without automatically resubmitting the question. Transient status-read failures may recover within that window.

An unresolved question keeps its pending marker. A later explicit attempt with the same file, page and question reuses that request ID. A final result clears only its own pending marker, whether reached directly or through Saved file answers. A newer question's marker is preserved, and storage cleanup or optional voice failures cannot hide a delivered answer.

Validation covers normal delivery, lost/stalled acknowledgements, stalled polls and bodies, transient reads, exhausted waiting, explicit same-question retry, history recovery, newer pending markers, cleanup failure and optional voice failure. File upload, file listing and original-file download behaviour are outside this change. Phone visual testing remains outstanding.
