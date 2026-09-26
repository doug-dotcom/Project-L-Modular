# Layer 174 — Claim-token mutation spine

Layer 174 carries the one-shot claim identity through every post-claim durable mutation. TaskStore verifies the token returned by the claim RPC, remembers it per worker, and supplies it to heartbeat/checkpoint, action journal, action reconciliation, rejection, terminal save and terminal reconciliation RPCs. Missing or mismatched tokens fail closed. Terminal completion or rejection clears the process-local token binding.

The production foundation migration is `20260926075023_project_l_layer174_claim_token_mutation_spine`. The tokenless bound RPCs are retired after runtime certification in the Layer 174 cutover migration.
