from pathlib import Path


SQL = Path(
    "contracts/foundation/"
    "project_l_external_roster_head_witness_v1.sql"
)
EDGE = Path(
    "contracts/foundation/project-l-trust-witness/index.ts"
)


def sql() -> str:
    return SQL.read_text(encoding="utf-8").lower()


def edge() -> str:
    return EDGE.read_text(encoding="utf-8").lower()


def test_foundation_roster_head_witness_uses_separate_vault_domain():
    value = sql()

    assert "project_l_external_roster_head_witness_hmac_v1" in value
    assert "project_l_roster_head_witness_state" in value
    assert "project_l_roster_head_witness_events" in value
    assert (
        "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
        "external-head-witness-quorum-monotonic-head-witness:v1"
        in value
    )
    assert "foundation-roster-head-witness-v1" in value


def test_foundation_roster_head_witness_is_high_water_and_idempotent():
    value = sql()

    assert "roster-head-witness-sequence-rollback" in value
    assert "roster-head-witness-sequence-equivocation" in value
    assert "roster-head-witness-sequence-skip" in value
    assert "roster-head-witness-generation-without-policy-change" in value
    assert "roster-head-witness-state-not-advanced" in value
    assert "'replayed',true" in value
    assert "for update" in value


def test_foundation_roster_head_tables_are_not_directly_exposed():
    value = " ".join(sql().split())

    assert "enable row level security" in value
    assert "revoke all on foundation.project_l_roster_head_witness_state" in value
    assert "revoke all on foundation.project_l_roster_head_witness_events" in value
    assert (
        "grant execute on function "
        "foundation.project_l_roster_head_witness_record_v1"
        in value
    )
    assert "to foundation_gateway" in value


def test_foundation_edge_exposes_only_bounded_roster_head_operations():
    value = edge()

    assert "external-roster-head-current" in value
    assert "external-roster-head-record" in value
    assert "project_l_roster_head_witness_current_v1" in value
    assert "project_l_roster_head_witness_record_v1" in value
    assert "set local role foundation_gateway" in value
    assert "decrypted_secret" not in value
