# Project L R&D Evidence — Public Schema Growth Guard

- **Project:** Project L
- **Captured:** 2026-10-01 (AEST)
- **Build:** Public Data API relation growth guard
- **Tags:** R&D, AI, memory, PostgreSQL, Supabase, PostgREST, reliability, architecture, commercialisation

## Objective / problem

During Project L production recovery on 1 October 2026, PostgREST repeatedly failed to build its schema cache with `PGRST002` and PostgreSQL `57014` timeouts. Live catalog inspection established that the exposed `public` schema contained approximately:
- **762 tables**;
- **67 views**;
- **465 exposed functions**.

The project control plane remained `ACTIVE_HEALTHY`, but Data API connectivity and even metadata/advisor reads became unreliable while PostgREST repeatedly introspected the large exposed catalog.

Source inspection also found multiple backend-only/service-role data structures historically created in `public`, even where direct browser access was revoked. Such objects still enlarge PostgREST's schema-cache surface.

## Technical uncertainty

It was uncertain how to stop further schema-cache growth without:
1. migrating hundreds of legacy objects during an active production recovery;
2. breaking current Supabase client/RPC contracts;
3. blocking legitimate future public API relations;
4. assuming that privilege revocation removes an object from PostgREST introspection.

## Hypothesis / intended approach

Prevent new exposed relations from being created accidentally while leaving legacy objects untouched for a later compatibility-tested migration.

For migration files dated 1 October 2026 or later:
- all new tables/views must name their schema explicitly;
- backend-only relations should use `private.*`;
- new `public.*` tables/views require a per-object review marker:
  `-- data-api-public-relation-approved: public.object_name`.

The marker documents exposure intent only. It does not replace RLS or privilege review.

## Change / experiment

Added:
- `tests/test_public_schema_growth_guard.py`;
- `docs/architecture/project-l-public-schema-budget.md`;
- CI gating for the schema-growth guard.

The guard checks:
- `create table`;
- `create view`;
- `create materialized view`;
- schema qualification for new relations;
- explicit approval markers for exceptional public relations.

Existing relations and migrations before the cutoff are grandfathered so this prevention layer does not rewrite production schema during an incident.

Public function creation is deliberately not blocked in this first layer because existing Project L RPCs use `create or replace function public.*`; static source inspection cannot reliably distinguish a new API signature from an idempotent replacement. Function-surface cleanup is deferred to a separate inventory.

## Production evidence

Observed during the incident:
- PostgREST `PGRST002`: could not query database for schema cache;
- repeated PostgreSQL `57014` statement timeouts;
- Data API RPCs returning HTTP 503/504;
- direct SQL/metadata/advisor reads intermittently timing out;
- exposed catalog count: 762 public tables + 67 public views + 465 functions.

A role-level recovery experiment separated application RPC timeout from PostgREST cache-build timeout:
- `service_role` explicitly pinned to 8 seconds;
- `authenticator` first raised to 20 seconds, then 60 seconds for schema-cache recovery;
- this stopped the immediate old timeout pattern but did not immediately restore PostgREST connectivity, confirming catalog/cache recovery requires structural follow-up rather than only longer application timeouts.

## Tests / evidence

- Branch: `project-l/public-schema-growth-guard-20261001`
- New guard test: `tests/test_public_schema_growth_guard.py`
- CI result: **PASS — 1,750 passed, 5 warnings, 13 subtests passed in 34.43s**.
- PR #262 merged as commit `8d562846a0e4fbdf99132d755feccb1d6f48dbb7`.
- The guard found no migration-created relation violations from the 1 October 2026 cutoff through the tested head.

## Failures / unexpected behaviour

Database catalog and role-inspection queries intermittently timed out during the investigation, preventing a safe live bulk inventory of legacy browser-inaccessible public relations. No bulk schema move was attempted while the database was unstable.

## Learning

Revoking browser privileges is not equivalent to removing an object from the Data API schema-cache surface. Backend-only tables can remain operationally expensive merely by living in an exposed schema.

Schema placement must therefore be treated as a reliability boundary as well as a security/design decision.

## Next step

Inventory legacy public relations in bounded batches once direct catalog access is stable, prioritising service-role-only tables for migration to `private`. Keep application role timeouts strict while treating PostgREST schema-cache recovery as a separate operational concern.

## Source artefacts

- `tests/test_public_schema_growth_guard.py`
- `docs/architecture/project-l-public-schema-budget.md`
- `.github/workflows/ci.yml`
- Supabase/PostgREST logs from 2026-10-01
- Supabase role-timeout recovery migrations applied during the incident

## Time / cost

Engineering time is evidenced by GitHub, CI and Supabase timestamps. No external monetary cost is claimed.
