from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928061000_project_l_layer192_trace_trust_antirollback.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer192_runtime_role_cannot_mutate_trust_tables_directly():
    sql = source()

    assert (
        "revoke insert, update, delete, truncate, references, trigger"
        in sql
    )
    assert "on public.shine_ai_trace_trust_state from service_role" in sql
    assert "on public.shine_ai_trace_trust_ledger from service_role" in sql
    assert "grant select on public.shine_ai_trace_trust_state to service_role" in sql
    assert "grant select on public.shine_ai_trace_trust_ledger to service_role" in sql
    assert "revoke execute on function public.shine_ai_trace_trust_bootstrap_v1" in sql
    assert "revoke execute on function public.shine_ai_trace_trust_advance_v1" in sql


def test_layer192_snapshot_cross_checks_append_only_high_water_mark():
    sql = source()

    assert "shine_ai_trace_trust_snapshot_v2" in sql
    assert "trust-generation-high-water-mismatch" in sql
    assert "trust-keyset-high-water-mismatch" in sql
    assert "order by to_generation desc, id desc" in sql


def test_layer192_bootstrap_is_genesis_only():
    sql = source()

    bootstrap = sql.split(
        "create or replace function public.shine_ai_trace_trust_bootstrap_v2",
        1,
    )[1].split(
        "create or replace function public.shine_ai_trace_trust_advance_v2",
        1,
    )[0]
    assert "p_generation <> 1" in bootstrap
    assert "'genesis-pin'" in bootstrap
    assert "out-of-band-pin" not in bootstrap


def test_layer192_advance_requires_atomic_monotonic_precondition():
    sql = source()

    advance = sql.split(
        "create or replace function public.shine_ai_trace_trust_advance_v2",
        1,
    )[1]
    assert "pg_advisory_xact_lock" in advance
    assert "p_next_generation <> p_expected_generation + 1" in advance
    assert "trace trust transition anti-rollback precondition mismatch" in advance
    assert "shine_ai_trace_trust_snapshot_v2()" in advance


def test_layer192_schema_stores_no_private_signing_material():
    sql = source()

    for token in ("private_key", "signing_private", "app_secret"):
        assert token not in sql
