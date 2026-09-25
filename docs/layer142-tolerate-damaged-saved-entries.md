# Layer 142 — tolerate malformed saved-task entries

Startup recovery and saved-answer review now require an array of entries with non-blank string request IDs before using those entries. Malformed containers or individual entries no longer prevent installing the Saved answers action or checking the remaining valid tasks. The legacy pending pointer receives the same request-ID check.

Validation is applied to the read view without rewriting the original browser data. Existing write paths and delivery verification retain their behaviour. This does not repair damaged records or recover answers whose request identifiers are missing.

Validation covers null and object containers, mixed valid and invalid entries, blank/numeric IDs, a valid legacy pointer, installed review controls, checks restricted to valid IDs and unchanged stored source data. Phone visual testing remains outstanding.
