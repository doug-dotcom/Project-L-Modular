# Project L R&D Evidence — Durable Dispatcher Recovery Backpressure

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** durable dispatcher recovery backpressure
- **Tags:** R&D, AI, memory, PostgreSQL, Supabase, PostgREST, backpressure, reliability, commercialisation

## Objective / problem

Shine AI v1.74.0 production promotion was blocked because its Project L predeploy memory smoke received repeated HTTP 503 responses. Project L remained live on `/health`, but owner-scoped memory retrieval was fail-closed.

Production evidence showed two concurrent pressure signals:
- the memory bridge first encountered an HTTP read timeout and then PostgREST `PGRST002` schema-cache failures;
- Project L's two durable dispatcher threads were independently polling the same degraded Data API and logging paired failures at each recovery interval.

## Technical uncertainty

It was uncertain whether Project L could reduce application-side database pressure during recovery without changing live owner-scoped recall, durable-task integrity rules, lease semantics, or security/trust gates.

## Hypothesis / intended approach

Keep the reusable `TaskRunner` default unchanged for compatibility, but instantiate the production server with one durable dispatcher slot instead of two.

This should halve production queue-poll/reap pressure from the durable dispatcher while preserving the same fail-closed claim, lease, heartbeat, request-binding and terminal-write contracts. The trade-off is reduced background durable-task concurrency.

## Change / experiment

`api/server.py` now constructs:

`TaskRunner(task_store, execute_durable_request, slots=1)`

No memory-retrieval timeout, circuit breaker, Project L recall contract, Shine AI trust gate or Supabase schema is relaxed.

## Tests / evidence

- regression added to `tests/test_durable_tasks.py` proving the production server explicitly uses one slot;
- the existing TaskRunner default remains two slots;
- Project L CI is required before merge.

## Production incident evidence

During the Shine AI v1.74.0 release attempt:
- Shine AI built successfully but its Project L bridge predeploy smoke exhausted six attempts with HTTP 503;
- Project L logs showed `HTTP_TIMEOUT` followed by `PGRST002 Could not query the database for the schema cache`;
- subsequent bridge calls were rejected quickly by the existing circuit breaker;
- Supabase PostgreSQL logs showed SQLSTATE `57014` statement cancellations from PostgREST in the same incident window;
- direct Supabase SQL, migration listing and migration application also terminated with connection timeouts;
- the already-merged semantic recovery cadence migration could not be applied because Supabase could not initialise its migration-history transaction.

## Failures / unexpected behaviour

A direct attempt to apply the existing semantic recovery cadence migration failed before application with a database connection timeout. No live database change is claimed.

The exact Shine AI v1.74.0 Railway redeploy also failed because the Project L bridge remained unavailable. No deployment bypass was introduced.

## Learning

When the shared data plane is unhealthy, retrying deployment or relaxing fail-closed memory gates is the wrong response. Backpressure should first reduce non-user-facing database demand while preserving the same trust and recall contracts.

## Next step

Run Project L CI. If green, merge this recovery-pressure reduction. Production deployment must still pass Project L's existing predeploy trust/memory checks. Only after Project L and its Supabase path recover should Shine AI v1.74.0 be redeployed and re-promoted.

## Source artefacts

- `api/server.py`
- `core/cognition/durable_tasks.py`
- `tests/test_durable_tasks.py`
- `supabase/migrations/20261001044500_project_l_semantic_recovery_cadence.sql`
- Shine AI failed Railway deployments `e6227281-787d-472a-b98c-7fb2e846f099` and `8091149f-b71a-470f-b222-89556c919efd`
- Project L Railway runtime logs
- Supabase operational logs

## Time / cost

Engineering time is evidenced by GitHub, Railway and Supabase timestamps. No external monetary cost is claimed.
