from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261001024000_project_l_semantic_background_yield.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_resource_limit_probe_bounds_recent_dispatches_before_pg_net_join():
    sql = source()

    assert "create or replace function private.project_l_semantic_recent_resource_limit_v1()" in sql
    assert "with recent_dispatches as materialized" in sql
    assert "where created_at >= now() - make_interval(" in sql
    assert "order by created_at desc" in sql
    assert "limit 64" in sql
    assert "join recent_dispatches d" in sql
    assert "on d.request_id = r.id" in sql
    assert "where r.status_code = 546" in sql
    assert "cross join private.l_semantic_worker_runtime_policy" not in sql


def test_resource_limit_probe_preserves_fail_closed_semantics_and_privileges():
    sql = source()

    assert "returns boolean" in sql
    assert "security definer" in sql
    assert "revoke all on function private.project_l_semantic_recent_resource_limit_v1()" in sql
    assert "from public, anon, authenticated;" in sql
    assert "to service_role;" in sql


def test_activation_preflight_is_staggered_away_from_semantic_worker():
    sql = source()

    assert "private.project_l_semantic_activation_preflight_v1()" in sql
    assert "and schedule = '*/15 * * * *'" in sql
    assert "schedule := '2-59/15 * * * *'" in sql
    assert sql.count("perform cron.alter_job(") == 1

    # This layer must not retune unrelated estate workloads.
    assert "rivers_" not in sql
    assert "fiona_" not in sql


def test_background_yield_reloads_postgrest_after_function_replacement():
    sql = source()
    assert sql.rfind("notify pgrst, 'reload schema';") > sql.rfind(
        "create or replace function"
    )
