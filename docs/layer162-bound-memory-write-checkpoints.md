# Layer 162 — Bound checkpoints before durable memory writes

Layer 162 tightens the durable-task boundary around Project L's memory persistence.

Layer 160 bound task heartbeats, checkpoints and result writes to the exact claimed request. Layer 161 removed the legacy unbound task mutation path. Layer 162 now requires a fresh bound checkpoint immediately before each durable memory-writing stage in the main chat path.

The guarded stages are:

- short-term user memory;
- raw user memory;
- the user-memory promotion / brain pipeline, including explicit intake;
- short-term assistant memory;
- raw assistant memory.

This closes the previous ordering gap where the short-term user write happened before the first durable-task checkpoint, and where multiple persistence operations could share one earlier checkpoint. If the lease or request binding has been lost, the checkpoint fails before the next guarded write can begin.

Cognitive working memory remains process-only and is not a durable database write. Reflective learning ingestion remains candidate-only and does not automatically store growth.

No database schema or external dependency changes are introduced. Regression tests assert the exact ordering of every persistence boundary and the Layer 162 release marker.
