# Layer 129 — saved-result check times

Each saved-result entry now shows when its check completed, using an Australian date format and the device timezone. A semantic time element also records the ISO timestamp. This is the check time, not the original answer date or a guarantee that its status is still current.

A failed retrieval is labelled Check attempted rather than Checked. Older batches retain their own check times, and refresh creates new timestamps. Search and filtering do not change timestamps or issue requests. Timestamps are displayed locally and are not written to task storage.

Validation covers separate batch times, unchanged times during filtering, refresh and failed attempts. Phone visual testing remains outstanding.
