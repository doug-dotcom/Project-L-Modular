from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928102500_project_l_layer202_quorum_policy_storage_stage.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer202_adds_authenticated_policy_storage_fields():
    sql = source()

    for column in (
        "state_sha256",
        "storage_auth_key_id",
        "storage_auth_tag",
    ):
        assert column in sql

    assert "shine_ai_witness_quorum_policy_snapshot_v2" in sql
    assert "witness-quorum-policy-storage-authentication-missing" in sql


def test_layer202_rotation_ledger_is_read_only_to_runtime_role():
    sql = source()

    assert (
        "create table if not exists "
        "public.shine_ai_witness_quorum_policy_storage_rotation_ledger"
        in sql
    )
    assert "enable row level security" in sql
    flat = " ".join(sql.split())
    assert (
        "grant select on "
        "public.shine_ai_witness_quorum_policy_storage_rotation_ledger "
        "to service_role"
        in flat
    )
    assert (
        "grant insert on "
        "public.shine_ai_witness_quorum_policy_storage_rotation_ledger "
        "to service_role"
        not in sql
    )


def test_layer202_seal_is_exact_and_idempotent():
    sql = source()
    seal = sql.split(
        "create or replace function "
        "public.shine_ai_witness_quorum_policy_seal_v2",
        1,
    )[1].split(
        "create or replace function "
        "public.shine_ai_witness_quorum_policy_rotate_storage_v2",
        1,
    )[0]

    assert "pg_advisory_xact_lock" in seal
    assert "seal precondition mismatch" in seal
    assert "already_sealed" in seal
    assert "state_sha256=p_state_sha256" in seal
    assert "storage_auth_key_id=p_storage_auth_key_id" in seal
    assert "storage_auth_tag=p_storage_auth_tag" in seal


def test_layer202_rotation_changes_only_storage_authentication_wrapper():
    sql = source()
    rotate = sql.split(
        "create or replace function "
        "public.shine_ai_witness_quorum_policy_rotate_storage_v2",
        1,
    )[1]

    assert "row_state.generation <> p_expected_generation" in rotate
    assert "row_state.policy_sha256 <> p_expected_policy_sha256" in rotate
    assert "row_state.state_sha256 <> p_expected_state_sha256" in rotate
    assert "set storage_auth_key_id=p_target_auth_key_id" in rotate
    assert "storage_auth_tag=p_storage_auth_tag" in rotate

    forbidden_updates = (
        "set generation=",
        "minimum_witnesses=",
        "accepted_witness_ids=",
        "previous_policy_sha256=",
        "policy_sha256=p_",
        "state_sha256=p_",
    )
    update_section = rotate.split(
        "update public.shine_ai_witness_quorum_policy_state",
        1,
    )[1].split("insert into", 1)[0]
    for token in forbidden_updates:
        assert token not in update_section


def test_layer202_stage_preserves_v1_bootstrap_until_runtime_cutover():
    sql = source()

    assert (
        "revoke execute on function "
        "public.shine_ai_witness_quorum_policy_bootstrap_v1"
        not in sql
    )


def test_layer202_schema_stores_tags_but_no_storage_secrets():
    sql = source()

    assert "storage_auth_tag" in sql
    for token in (
        "storage_secret",
        "private_hmac",
        "redis_url",
        "app_secret",
    ):
        assert token not in sql
