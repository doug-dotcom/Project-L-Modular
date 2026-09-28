from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928213000_project_l_layer206_external_witness_roster_storage_rotation.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer206_rotation_mutates_only_storage_authentication_fields():
    sql = source()

    assert "shine_ai_external_witness_roster_rotate_storage_v1" in sql
    assert "set storage_auth_key_id = p_target_storage_auth_key_id" in sql
    assert "storage_auth_tag = p_target_storage_auth_tag" in sql

    forbidden_setters = (
        "set generation =",
        "set minimum_witnesses =",
        "set accepted_witness_ids =",
        "set previous_policy_sha256 =",
        "set policy_sha256 =",
        "set state_sha256 =",
    )
    for token in forbidden_setters:
        assert token not in sql


def test_layer206_rotation_requires_exact_state_preconditions():
    sql = source()

    assert "row_state.generation <> p_expected_generation" in sql
    assert "row_state.policy_sha256 <> p_expected_policy_sha256" in sql
    assert "row_state.state_sha256 <> p_expected_state_sha256" in sql
    assert (
        "row_state.storage_auth_key_id <> p_expected_storage_auth_key_id"
        in sql
    )
    assert "for update" in sql
    assert "pg_advisory_xact_lock" in sql


def test_layer206_rotation_is_idempotent_only_for_same_target_tag():
    sql = source()

    assert "already_rotated" in sql
    assert "external witness roster target key tag mismatch" in sql
    assert "external witness roster rotation source key mismatch" in sql


def test_layer206_rotation_rpc_is_service_role_only():
    sql = source()

    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
