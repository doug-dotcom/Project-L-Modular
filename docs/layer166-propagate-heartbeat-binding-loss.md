# Layer 166 — Propagate definitive heartbeat binding loss

Layers 160–165 bind durable execution, memory writes and connected actions to the exact claimed request. Layer 166 closes the remaining coordination gap between the heartbeat thread and the main execution thread.

Previously, if a bound heartbeat RPC returned `false`, the heartbeat thread simply exited. That definitively meant the worker no longer owned the task, but the main execution thread would only discover the loss when a later database checkpoint happened to run.

Layer 166 adds a shared cooperative binding-loss signal to the live durable-task context.

- A definitive heartbeat rejection sets the shared signal immediately.
- Every later `checkpoint(...)` checks the signal before making another database call.
- If the signal is already set, the checkpoint stops locally with `DurableTaskBindingError`.
- A checkpoint that itself discovers lost ownership also sets the shared signal.
- After a long-running execution call returns, the runner checks the signal before treating the result as successful.
- A heartbeat transport exception does **not** set the signal because network uncertainty does not prove ownership was lost; the next bound checkpoint still verifies against the database.
- The layer is cooperative only: it does not claim to interrupt a model call or provider call that is already in progress.

Production runners use a six-part task context containing the existing exact request binding plus the shared event. Existing five-part synthetic/manual bindings remain supported for compatibility.

No database schema, RPC, dependency or external service change is required.
