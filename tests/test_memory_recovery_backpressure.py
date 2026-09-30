from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20260930030000_project_l_memory_recovery_cron_backpressure.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_backpressure_only_retunes_known_project_l_and_shine_me_minute_workers():
    sql = source()
    expected_workers = {
        "private.project_l_semantic_cron_tick_v1()": "*/5 * * * *",
        "private.me_enqueue_due_trust_recovery_v1(20)": "1-59/5 * * * *",
        "private.me_harvest_trust_recovery_v1(50)": "2-59/5 * * * *",
        "private.me_reconcile_pending_activations_v1(50)": "3-59/5 * * * *",
        "private.me_observe_activation_reconciliation_lifecycle_v1(120)": "4-59/5 * * * *",
        "private.me_observe_activation_burn_episode_v1()": "*/5 * * * *",
        "private.me_correlate_activation_operational_events_v1(300)": "1-59/5 * * * *",
    }

    assert "update cron.job" not in sql
    assert sql.count("perform cron.alter_job(") == len(expected_workers)
    assert sql.count("select jobid") == len(expected_workers)
    assert sql.count("and schedule = '* * * * *'") == len(expected_workers)

    for worker, schedule in expected_workers.items():
        assert worker in sql
        assert f"schedule := '{schedule}'" in sql

    assert "rivers_" not in sql
    assert "fiona_" not in sql


def test_backpressure_reloads_postgrest_after_cadence_repair():
    sql = source()
    assert sql.rfind("notify pgrst, 'reload schema';") > sql.rfind(
        "perform cron.alter_job("
    )
