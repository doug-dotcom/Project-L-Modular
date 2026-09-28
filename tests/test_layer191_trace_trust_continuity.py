from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928052000_project_l_layer191_shine_ai_trace_trust_continuity.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer191_trust_tables_are_rls_service_role_only():
    sql = source()

    assert "create table if not exists public.shine_ai_trace_trust_state" in sql
    assert "create table if not exists public.shine_ai_trace_trust_ledger" in sql
    assert "enable row level security" in sql
    assert "revoke all on public.shine_ai_trace_trust_state from anon, authenticated" in sql
    assert "revoke all on public.shine_ai_trace_trust_ledger from anon, authenticated" in sql
    assert "to service_role" in sql


def test_layer191_transition_is_atomic_monotonic_and_append_only():
    sql = source()

    assert "shine_ai_trace_trust_bootstrap_v1" in sql
    assert "shine_ai_trace_trust_advance_v1" in sql
    assert "p_next_generation <> p_expected_generation + 1" in sql
    assert "for update" in sql
    assert "trace trust transition precondition mismatch" in sql
    assert "insert into public.shine_ai_trace_trust_ledger" in sql
    assert "grant select, insert on public.shine_ai_trace_trust_ledger to service_role" in sql
    assert "grant update" not in sql.split(
        "public.shine_ai_trace_trust_ledger"
    )[1].split("create or replace function", 1)[0]


def test_layer191_ledger_stores_no_private_signing_material():
    sql = source()

    forbidden = (
        "private_key",
        "signing_private",
        "app_secret",
        "service_role_key",
    )
    for token in forbidden:
        assert token not in sql

    assert "authorization_public_key_sha256" in sql
    assert "certificate_sha256" in sql
    assert "trusted_keyset jsonb" in sql
