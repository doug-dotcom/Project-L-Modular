from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928230000_project_l_layer209_external_roster_head_history.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer209_history_requires_contiguous_generations():
    sql = source()

    assert "shine_ai_external_witness_roster_history_v1" in sql
    assert "external-witness-roster-generation-count-mismatch" in sql
    assert "external-witness-roster-generation-gap" in sql
    assert "external-witness-roster-history-link-invalid" in sql
    assert "external-witness-roster-high-water-mismatch" in sql


def test_layer209_history_does_not_expose_hmac_or_authorization_bodies():
    sql = source()

    history = sql.split(
        "create or replace function "
        "public.shine_ai_external_witness_roster_history_v1",
        1,
    )[1].split(
        "create or replace function "
        "public.shine_ai_external_witness_roster_snapshot_v1",
        1,
    )[0]
    assert "'statesha256'" in history
    assert "'authorizationsha256'" in history
    assert "'authorizingwitnessids'" in history
    assert "'storage_auth_tag'" not in history
    assert "'authorizations'," not in history


def test_layer209_snapshot_supports_multiple_roster_generations():
    sql = source()

    snapshot = sql.split(
        "create or replace function "
        "public.shine_ai_external_witness_roster_snapshot_v1",
        1,
    )[1]
    assert "shine_ai_external_witness_roster_history_v1()" in snapshot
    assert "v_ledger_count <> 1" not in snapshot


def test_layer209_history_is_service_role_only():
    sql = " ".join(source().split())

    assert (
        "revoke all on function "
        "public.shine_ai_external_witness_roster_history_v1()"
        in sql
    )
    assert (
        "grant execute on function "
        "public.shine_ai_external_witness_roster_history_v1()"
        in sql
    )
    assert "to service_role" in sql
