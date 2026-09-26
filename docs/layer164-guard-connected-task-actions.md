# Layer 164 — Revalidate durable binding before connected write actions

Layer 163 guarded each live memory-promotion insert. Layer 164 extends the same request-binding rule to the current connected capability surface.

Project L's Gmail and Calendar adapters are read-only. The Google Tasks adapter can create an external task, so task creation is treated as an action boundary.

For durable chat execution:

- the server passes the live durable-task checkpoint into capability routing;
- Google Tasks invokes that guard immediately before `tasks.insert(...).execute()`;
- the guard revalidates worker lease, input hash and exact claimed request through the bound task RPC;
- `DurableTaskBindingError` is re-raised by the capability router and the server instead of being converted into an ordinary service-error response;
- if binding is lost, the external task is not created.

Read-only task listing does not invoke the write guard. Gmail, Calendar and external research behaviour is unchanged.

Regression coverage verifies guard-before-insert ordering, zero external inserts after a synthetic binding loss, router propagation of binding loss, read-only compatibility, server wiring, and release continuity.

No database schema or external dependency change is required.
