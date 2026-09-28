from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928225000_project_l_layer209_roster_head_material.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_roster_head_material_requires_contiguous_history():
    sql = source()

    assert "external-roster-head-history-empty" in sql
    assert "external-roster-head-history-gap" in sql
    assert "v_min<>1 or v_max<>v_count" in sql


def test_roster_head_material_binds_transition_evidence():
    sql = source()

    assert "shine_ai_external_roster_transition_evidence" in sql
    assert "external-roster-head-history-evidence-mismatch" in sql
    assert "acceptance_mode<>'previous-roster-quorum'" in sql
    assert "e.authorization_sha256<>l.authorization_sha256" in sql
    assert "e.authorizing_witness_ids<>l.authorizing_witness_ids" in sql


def test_genesis_cannot_carry_transition_authority():
    sql = source()

    assert "l.acceptance_mode<>'genesis-pin'" in sql
    assert "l.previous_policy_sha256 is not null" in sql
    assert "l.authorization_sha256 is not null" in sql
    assert "l.authorizing_witness_ids is not null" in sql


def test_rpc_returns_only_bounded_stable_head_inputs():
    sql = source()

    assert "'sequence',l.generation" in sql
    assert "'generation',l.generation" in sql
    assert "'previouspolicysha256',l.previous_policy_sha256" in sql
    assert "'policysha256',l.policy_sha256" in sql
    assert "'statesha256',l.state_sha256" in sql
    assert "to service_role" in sql
