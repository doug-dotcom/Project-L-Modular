# Layer 165 — Request-bound connected action receipts

Layer 164 revalidated the durable task binding immediately before Google Tasks creation. Layer 165 adds the matching audit proof after the provider confirms the action.

A Google Tasks create result now emits a compact action receipt containing:

- receipt protocol version;
- confirmed status;
- the current durable request ID and whether the receipt is request-bound;
- capability and action type;
- the provider resource ID returned by Google;
- a SHA-256 of the exact task title instead of duplicating the title text;
- a canonical receipt SHA-256 covering the complete receipt body.

The capability router verifies the receipt against the currently bound durable request before treating the action as a clean success. If Google reports success but does not return a usable resource ID, L reports the action as uncertain and tells the user to check Google Tasks before retrying.

The action receipt is included in the existing capability route, so the final delivery seal covers it. Project L also performs independent semantic receipt verification:

- before a durable result can be saved;
- when a durable saved answer is recovered;
- before a direct/non-durable cached result is stored.

A receipt rebound to another request, structurally changed, or hash-tampered is rejected even if an outer payload was otherwise self-consistent.

Read-only capabilities and replies without connected actions remain compatible. No database schema or external dependency change is required.
