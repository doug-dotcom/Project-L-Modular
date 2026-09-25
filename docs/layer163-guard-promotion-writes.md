# Layer 163 — Revalidate durable binding inside memory promotion

Layer 162 added fresh request-bound checkpoints immediately before each top-level user and assistant memory persistence stage. Layer 163 carries that protection inside the governed user-memory promotion pipeline itself.

The live promotion path can create several durable records from one verified raw user message:

- the canonical long-term memory record;
- an episodic memory when a dated event qualifies;
- an identity anchor when a stable first-person truth qualifies;
- governed learning storage when Doug explicitly states a learning observation.

Each actual insert now invokes the live durable-task checkpoint immediately before the write. The checkpoint revalidates the worker lease, immutable input hash and exact claimed request through the bound task RPC.

A dedicated `DurableTaskBindingError` distinguishes task ownership/binding loss from ordinary storage errors. Binding loss is never converted into a recoverable specialised-memory or learning-store error, and the server's memory-pipeline wrapper re-raises it so the durable task stops instead of continuing.

Non-durable maintenance/backfill callers remain compatible: the write guard is optional and their existing behaviour is unchanged.

Regression coverage verifies:
- every live promotion insert is preceded by its own guard;
- a binding loss before an identity-anchor write prevents that write and all later learning storage;
- a binding loss before governed learning is propagated rather than downgraded;
- the server passes the real bound checkpoint into the promotion pipeline and propagates binding loss;
- the Layer 163 release marker is continuous.

No database schema or external dependency change is required.
