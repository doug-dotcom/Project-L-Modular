# Layer 171 — Token-bound durable claims

Layer 171 closes the claim-side acknowledgement window in the durable task queue.

Before this layer, a claim could commit in Postgres while its RPC response was lost. The dispatcher deliberately avoided an immediate blind retry, but a later poll under the same worker could still attempt to claim new work while the first claim remained unresolved.

## Contract

Every dispatcher claim attempt now carries a fresh one-shot UUID claim token.

- the token is generated before the claim RPC;
- if the claim response is transport-ambiguous, the dispatcher retains the same token across retries;
- replaying the same worker + token returns only the exact still-live claim;
- a different token cannot claim more work while that worker already owns a live task;
- one worker can have at most one running task at the database level;
- one claim token can identify at most one task for its entire lifetime;
- a token that reached terminal or interrupted state cannot be reused to claim another task;
- expired work is still interrupted rather than replayed automatically;
- once the claim RPC returns successfully, including an empty queue response, that token is consumed locally and the next poll gets a fresh token.

The application never uses a different task as a substitute for an ambiguous claim.

## Database boundary

Layer 171 adds:

- public.l_chat_tasks.claim_token;
- a unique partial index over non-null claim tokens;
- a unique partial index enforcing at most one running task per worker;
- public.l_task_claim_bound(worker, claim_token), a SECURITY INVOKER backend-only RPC.

The new function remains service-role only and preserves the existing RLS/private backend boundary.

The production migration is 20260926065344_project_l_layer171_token_bound_claims.
