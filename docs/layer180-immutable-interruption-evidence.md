# Layer 180 — Database-immutable interruption evidence

Layer 178 created forensic interruption evidence and Layer 179 verifies it during recovery. Layer 180 makes that evidence immutable at the database boundary.

A BEFORE UPDATE trigger on l_chat_tasks permits the interruption evidence to transition from null only when the row itself transitions from running to interrupted and the evidence agrees with the old checkpoint, worker, claim token and action-journal presence.

Once interruption_evidence is non-null, any attempt to change or erase it raises a PostgreSQL check-violation error.

The trigger function itself is not directly executable by public, anon, authenticated or service_role; it is invoked only by the table trigger.

Production migration: `20260926120744_project_l_layer180_immutable_interruption_evidence`.
