# Project L Public Schema Budget

## Purpose

Project L's Supabase Data API currently exposes a very large `public` schema.
PostgREST must introspect every exposed table, view and function when it builds
its schema cache. During the 1 October 2026 recovery work, the live project had
approximately 762 public tables, 67 public views and 465 exposed functions, and
PostgREST repeatedly failed schema-cache rebuilds with `PGRST002` and
PostgreSQL `57014` timeouts.

This policy prevents Project L from expanding that relation surface by accident
while legacy objects are reviewed for migration to private schemas.

## Rule from 1 October 2026

New migration-created tables and views must always use an explicit schema.

- Backend-only storage defaults to `private.*`.
- A new `public.*` table or view is exceptional.
- Every exceptional public relation needs a per-object review marker in the
  migration:

```sql
-- data-api-public-relation-approved: public.example_api_table
create table public.example_api_table (...);
```

The marker records intent; it is not a security grant. RLS, privileges and
service-role boundaries still require their normal independent review.

## Why functions are not blocked by this first guard

Project L already uses public service-role RPC wrappers as its Data API
interface. Static source inspection cannot safely distinguish a new RPC
signature from an idempotent `create or replace function` of an existing
signature. Function-surface reduction therefore needs a separate inventory
and migration rather than an unsafe blanket ban.

## Legacy scope

Relations created before the cutoff are grandfathered by this guard. Their
presence is not endorsed. The next cleanup phase should inventory backend-only
public relations and move them to `private` in bounded, compatibility-tested
batches.
