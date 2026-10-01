from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261001044500_project_l_semantic_recovery_cadence.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_semantic_recovery_cadence_reduces_only_project_l_background_jobs():
    sql = source()

    assert "private.project_l_semantic_cron_tick_v1()" in sql
    assert "private.project_l_semantic_circuit_breaker_v1()" in sql
    assert "schedule := '7-59/15 * * * *'" in sql
    assert "schedule := '12-59/15 * * * *'" in sql
    assert sql.count("and schedule = '*/5 * * * *'") == 2
    assert sql.count("perform cron.alter_job(") == 2

    assert "project_l_semantic_activation_preflight_v1" not in sql
    assert "fiona_" not in sql
    assert "rivers_" not in sql
    assert "private.me_" not in sql


def test_semantic_recovery_cadence_uses_supported_cron_surface_and_reload():
    sql = source()

    assert "update cron.job" not in sql
    assert sql.count("select jobid") == 2
    assert "notify pgrst" not in sql.lower()
    assert "reload schema" not in sql.lower()
