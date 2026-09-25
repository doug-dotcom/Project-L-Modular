# Layer 157 — Bind document answers to the exact source request

Document-evidence answers are now checked against the durable request that produced them. A successful answer must carry the same document ID, physical page and immutable source SHA-256 as the submitted request, with a readable source filename.

The binding is enforced twice. Before a document answer is written to the durable task result, a mismatch fails closed and the mismatched answer is not persisted as ready. When a saved ready answer is recovered later, the stored request and result are checked again so stale or tampered source metadata cannot be presented as a valid file answer.

Normal chat tasks are unchanged. The raw durable request is used internally for verification and is not added to the recovered API payload. This complements delivery and answer-provenance verification: request identity alone does not prove that a file answer still points to the file and page that were actually asked about.

Regression coverage includes matching bindings, document/page/hash/filename mismatches, missing evidence, non-document compatibility, write-time rejection and read-time rejection. No schema change or external dependency is introduced.
