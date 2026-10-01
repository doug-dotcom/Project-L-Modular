# Project L R&D Evidence — Cron Cadence Without PostgREST Reload

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** PostgREST reload discipline for semantic cron recovery
- **Tags:** R&D, AI, memory, PostgreSQL, Supabase, PostgREST, cron, reliability, deployment-safety, commercialisation

## Objective / problem

The source migration that reduces Project L semantic cron pressure was still not live because the database was intermittently unable to accept direct SQL or initialise Supabase migration history. During the same incident, PostgREST was repeatedly failing schema-cache rebuilds across a very large exposed public schema.

Inspection of the pending cadence migration found that it ended with:

`notify pgrst, 'reload schema';`

even though the migration changes only pg_cron schedules and does not add, remove or replace any PostgREST-visible table, view or routine.

## Technical uncertainty

It was uncertain whether leaving the reload in the pending migration could worsen recovery by triggering another expensive schema-cache rebuild at the same moment the cadence reduction finally becomes writable.

## Hypothesis / intended approach

Cron schedule changes do not require PostgREST schema introspection. Remove the schema reload from the not-yet-live migration and make that absence an explicit regression contract.

This preserves the intended cadence change while avoiding an unnecessary Data API cache rebuild.

## Change / experiment

Modified:
- `supabase/migrations/20261001044500_project_l_semantic_recovery_cadence.sql`;
- `tests/test_semantic_recovery_cadence.py`.

The migration now ends after the two `cron.alter_job()` operations and documents that no PostgREST reload is required.

The regression test now requires:
- no `notify pgrst`;
- no `reload schema`.

## Production evidence

Before this source correction:
- jobs 117 and 119 remained active on `*/5 * * * *`;
- logs proved both jobs started and timed out at approximately 04:45, 04:50 and 04:55 UTC;
- the intended 15-minute cadence was not yet live;
- direct attempts to apply the cadence change failed due database connection timeout;
- PostgREST continued reporting `PGRST002` schema-cache failures;
- the exposed catalog was approximately 762 public tables, 67 public views and 465 functions.

Because the cadence migration has not successfully applied live, correcting its source before the eventual successful application does not claim or overwrite a verified production migration.

## Tests / evidence

- Branch: `project-l/cron-cadence-no-postgrest-reload-20261001`
- CI result: **PASS — 1,750 passed, 5 warnings, 13 subtests passed in 32.10s**.
- PR #265 merged as commit `37ab12f5bc3a62b051ed5a878889f1f747102426`.

## Failures / unexpected behaviour

Several live SQL write attempts failed from connection timeout before commit. The write was explicitly verified as not applied: jobs 117 and 119 still reported `*/5 * * * *`.

## Learning

Operational configuration changes should not trigger PostgREST schema rebuilds unless the Data API schema surface actually changed. During cache pressure, unnecessary reload notifications can convert a harmless cron retune into another expensive catalog-introspection event.

## Next step

Apply the cadence update directly when a database connection is reliably available, omitting any PostgREST reload. Verify jobs 117 and 119 by reading their schedules back. Until then, do not claim the 15-minute cadence is live.

## Source artefacts

- `supabase/migrations/20261001044500_project_l_semantic_recovery_cadence.sql`
- `tests/test_semantic_recovery_cadence.py`
- Supabase/PostgreSQL cron logs for jobs 117 and 119
- Project L Data API recovery evidence

## Time / cost

Engineering time is evidenced by GitHub, CI and Supabase timestamps. No external monetary cost is claimed.
