# L Unlimited Stage 2: durable chat tasks

Browser chat previously stored pending work and replies in a ten-minute process cache.
A process restart lost both. `/chat/start` now commits a task to Supabase before
acknowledging it. Two background workers atomically claim queued tasks with
`FOR UPDATE SKIP LOCKED`, record progress, renew a two-minute lease every 15 seconds,
and save the final answer including Stage 1's evidence receipt.

## Recovery behaviour

- Queued tasks survive restart and are picked up by the new process.
- Completed answers persist without the previous ten-minute expiry.
- Running tasks whose lease expires become `interrupted`. They are never automatically
  replayed: an external action or memory write may already have happened.
- Execution failures become `failed`; result-write failures retry only the idempotent
  database write, up to three attempts. A prolonged database outage can still lose an
  unsaved answer; the task remains visible as interrupted after its lease expires.
- Reusing the same request ID and message returns its existing status. Changing the
  request body returns 409. A different recovery owner receives 404.
- Browser reload reconnects pending tasks. **Saved answers** reopens the latest 20
  locally indexed requests; up to 100 request handles are retained in that browser.
  Clearing browser storage loses those recovery handles and the recovery secret.

This is durable request/result storage with progress checkpoints, not arbitrary
mid-instruction resumption or exactly-once execution of external effects. A manually
resent request with a new ID is new work. Direct legacy `/chat` API calls and image
upload tasks retain their existing behaviour. Persistent uploaded originals belong
to roadmap Stage 7.

## Access model

The existing application does not authenticate chat requests with Supabase Auth.
Stage 2 therefore uses a random 256-bit browser recovery capability, passed in
`X-L-Recovery-Token`, never in a URL. Only SHA-256 of that secret is stored. `user_id`
is a UUID derived from the capability hash; it is an opaque browser principal, **not
proof of a person's identity**. This does not introduce account authentication or
isolate the application's pre-existing personal-memory retrieval.

The new task table has RLS enabled and grants revoked from PUBLIC, anon and authenticated.
Only the existing backend service role can access it. All four RPCs are SECURITY INVOKER,
have fixed empty search paths, and EXECUTE restricted to service_role. Owner filters
are applied server-side on every durable-result lookup. Durable replies never enter
the unprotected legacy result cache. No service key is sent to the browser.
The advisor's `rls_enabled_no_policy` INFO for this table is intentional default-deny;
no client policies are appropriate for this backend-only table.

## Deployment and validation

Schema source: `supabase/migrations/20260905101518_durable_chat_tasks.sql`, created
with the Supabase CLI and deployed through the managed migration `durable_chat_tasks`.
Apply the schema once before deploying the application.
No existing data tables are changed. No provider credentials or models change.

Run `python -m pytest -q tests/test_durable_tasks.py tests/test_durable_ui.py` plus the
active CI regression suite. Database transaction assertions cover deduplication,
conflicts, worker ownership, terminal states, expired leases and client privileges.
Live verification must cover start/poll, wrong-token denial, duplicate submission,
and saved-result retrieval after replacing the application process.

Rollback the application commit without dropping the task table. Saved task data
remain available for a subsequent corrected deployment; the old UI cannot recover them.

References: [Supabase functions](https://supabase.com/docs/guides/database/functions),
[Python RPC](https://supabase.com/docs/reference/python/rpc),
[RLS](https://supabase.com/docs/guides/database/postgres/row-level-security),
[default-deny advisor](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
