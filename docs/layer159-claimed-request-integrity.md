# Layer 159 — Verify claimed durable requests before execution

A durable task worker now receives an explicit request-integrity result from the real TaskStore claim boundary before the request reaches cognition or any action-capable execution path.

TaskStore recomputes the canonical request hash returned by the database claim and verifies the embedded request ID against the claimed row. If the request body, request ID or stored input hash is inconsistent, the runner fails the task before execution. No model call, checkpoint, connected action or user-visible task side effect is allowed to start from that invalid claim.

The rejection path records a fixed failure message and logs only the request ID plus fixed integrity issue codes; request content is not logged. Existing direct unit fixtures that bypass TaskStore remain compatible because they do not claim to represent a verified database claim.

This extends Layer 158 from recovery-time verification to execution-time verification. No schema change or external dependency is required.
