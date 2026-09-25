# Layer 158 — Verify the stored durable request before recovery

Every production durable-task read now retrieves the stored request and its non-null input hash, recomputes the canonical request hash, and checks that the embedded request ID still matches the row being recovered.

A missing or malformed request, malformed input hash, changed request body or request-ID mismatch fails closed before delivery, answer-provenance or document-source verification can legitimise the saved result. The recovery response exposes only fixed verification state and issue codes; the stored request and input hash are removed before returning the payload.

This strengthens Layer 157 by making its document-source binding depend on a verified durable request. It also protects ordinary durable chat recovery. Existing synthetic/pre-contract readers that do not select either request column are labelled `legacy_unchecked` rather than falsely reported as verified; the production query always selects both fields, and the database schema has stored them as non-null since durable tasks were introduced.

Regression coverage includes exact matches, missing/malformed requests, request-ID substitution, malformed hashes, changed request contents, privacy of returned data and explicit legacy-reader compatibility. No schema change or new dependency is required.
