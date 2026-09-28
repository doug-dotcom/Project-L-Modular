from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928062500_project_l_layer193_authenticated_trust_storage_stage.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer193_adds_authenticated_state_columns():
    sql = source()

    for column in (
        "state_sha256",
        "storage_auth_key_id",
        "storage_auth_tag",
    ):
        assert column in sql

    assert "shine_ai_trace_trust_snapshot_v3" in sql
    assert "trust-state-authentication-missing" in sql


def test_layer193_seal_is_exact_and_idempotent():
    sql = source()

    seal = sql.split(
        "create or replace function public.shine_ai_trace_trust_seal_v3",
        1,
    )[1].split(
        "create or replace function public.shine_ai_trace_trust_bootstrap_v3",
        1,
    )[0]
    assert "pg_advisory_xact_lock" in seal
    assert "trace trust seal precondition mismatch" in seal
    assert "already_sealed" in seal
    assert "state_sha256 = p_state_sha256" in seal
    assert "storage_auth_tag = p_storage_auth_tag" in seal


def test_layer193_observe_only_changes_same_generation_state():
    sql = source()

    observe = sql.split(
        "create or replace function public.shine_ai_trace_trust_observe_v3",
        1,
    )[1].split(
        "create or replace function public.shine_ai_trace_trust_advance_v3",
        1,
    )[0]
    assert "trace trust observation anti-rollback mismatch" in observe
    assert "generation = p_expected_generation" in observe
    assert "keyset_sha256 = p_expected_keyset_sha256" in observe
    assert "trusted_keyset = p_trusted_keyset" in observe


def test_layer193_advance_commits_authentication_in_same_transaction():
    sql = source()

    advance = sql.split(
        "create or replace function public.shine_ai_trace_trust_advance_v3",
        1,
    )[1]
    assert "shine_ai_trace_trust_advance_v2" in advance
    assert "state_sha256 = p_state_sha256" in advance
    assert "storage_auth_key_id = p_storage_auth_key_id" in advance
    assert "storage_auth_tag = p_storage_auth_tag" in advance
    assert "trace trust v3 advance authentication commit failed" in advance


def test_layer193_staged_cutover_keeps_v2_runtime_available():
    sql = source()

    # Stage 1 deliberately does not revoke v2 yet; a post-deploy cleanup
    # migration retires v2 only after the v3 image is production healthy.
    assert (
        "revoke execute on function public.shine_ai_trace_trust_advance_v2"
        not in sql
    )
    assert (
        "revoke execute on function public.shine_ai_trace_trust_bootstrap_v2"
        not in sql
    )


def test_layer193_schema_stores_tags_not_hmac_secrets():
    sql = source()

    assert "storage_auth_tag" in sql
    for token in (
        "storage_secret",
        "private_hmac",
        "redis_url",
        "app_secret",
    ):
        assert token not in sql
