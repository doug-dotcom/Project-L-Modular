# Layer 181 — Immutable connected-action journal

Layer 181 makes the durable connected-action receipt write-once at the database boundary.

The first action receipt may be recorded only while the task remains running, when the receipt is confirmed, its request ID matches the task, it has a non-empty provider resource ID, and the same update advances the checkpoint to connected_action_recorded.

Once action_receipt is non-null, any attempt to change or erase it raises PostgreSQL check violation 23514.

This protects provider-confirmed external side effects even from privileged direct table updates and complements Layers 167–170, which already bind normal journal/terminal RPCs.

Production migration: `20260926122243_project_l_layer181_immutable_action_journal`.
