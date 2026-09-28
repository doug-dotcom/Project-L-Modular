from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928065500_project_l_layer193_retire_v2_trust_surface.sql"
)


def test_layer193_cleanup_retires_service_role_v2_trust_rpcs():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert (
        "revoke execute on function "
        "public.shine_ai_trace_trust_snapshot_v2()"
        in sql
    )
    assert (
        "revoke execute on function "
        "public.shine_ai_trace_trust_bootstrap_v2(integer,text,jsonb)"
        in sql
    )
    assert (
        "revoke execute on function "
        "public.shine_ai_trace_trust_advance_v2("
        "integer,text,integer,text,jsonb,text,text,text)"
        in sql
    )
    assert sql.count("from service_role") == 3


def test_layer193_cleanup_keeps_v3_recovery_surface():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for name in (
        "shine_ai_trace_trust_snapshot_v3",
        "shine_ai_trace_trust_seal_v3",
        "shine_ai_trace_trust_bootstrap_v3",
        "shine_ai_trace_trust_observe_v3",
        "shine_ai_trace_trust_advance_v3",
    ):
        assert f"revoke execute on function public.{name}" not in sql
