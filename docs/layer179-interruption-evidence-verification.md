# Layer 179 — Interruption evidence verification

Layer 179 closes the forensic loop created by Layer 178.

Recovery no longer treats interruption evidence as an informational JSON blob. Persisted interrupted tasks must carry a structurally valid Layer-178 evidence object whose facts agree with the recovered row:

- status is interrupted;
- reason is lease_expired;
- evidence version is 1.0;
- expired lease matches the preserved lease;
- checkpoint matches the preserved checkpoint;
- action_journalled matches whether a durable action receipt exists;
- worker ID and claim token are valid UUIDs;
- interruption timestamp is present.

A persisted interrupted row with missing or contradictory evidence fails recovery closed.

There is one intentional race-safe exception: recovery may observe a running row whose lease has expired before the bounded reaper commits the interruption. That read is surfaced as interrupted with interruption_integrity.status=pending_reaper rather than fabricating evidence that does not yet exist.
