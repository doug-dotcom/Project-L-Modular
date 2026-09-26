# Layer 168 — Preserve journaled actions on terminal failure

Layer 167 made provider-confirmed connected actions durable before the final answer is saved. Layer 168 closes the next failure window: an execution error after a successful journal write must terminate immediately with the same action receipt instead of leaving the task running until lease expiry.

## Contract

After a connected action is successfully journaled:

- the runtime freezes a process-local copy of the exact journaled receipt;
- later mutation of the caller's receipt object cannot change that copy;
- if execution subsequently raises, the terminal failure payload carries the exact same action receipt;
- the receipt is independently verified against the current request before being embedded in the failure route;
- the existing Layer 167 database contract then accepts the failed terminal result because its receipt exactly matches the durable journal;
- if the terminal write is rejected, the runner logs that the failure was not persisted instead of assuming success;
- process-local receipt state is cleared when the worker finishes.

If execution fails before any connected action is journaled, the failure path remains action-free and does not invent a receipt.

This layer does not change the existing rule for an uncertain action-journal transport response: uncertainty after a provider action remains fail-closed rather than being guessed into success.

No database schema, RPC or external dependency change is required.
