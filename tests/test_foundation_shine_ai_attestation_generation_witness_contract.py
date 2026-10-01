from pathlib import Path

SQL = Path("contracts/foundation/shine_ai_attestation_generation_witness_v1.sql")
EDGE = Path("contracts/foundation/project-l-trust-witness/index.ts")


def sql() -> str:
    return SQL.read_text(encoding="utf-8").lower()


def edge() -> str:
    return EDGE.read_text(encoding="utf-8").lower()


def test_attestation_generation_witness_is_independent_and_monotonic():
    value = sql()

    assert "shine_ai_attestation_generation_witness_state" in value
    assert "shine_ai_attestation_generation_witness_events" in value
    assert "shine_ai_attestation_generation_witness_hmac_v1" in value
    assert "attestation-generation-witness-rollback" in value
    assert "attestation-generation-witness-fork" in value
    assert "attestation-generation-witness-skip" in value
    assert "foundation-supabase-vault-hmac" in value
    assert "for update" in value
    assert "pg_advisory_xact_lock" in value


def test_attestation_generation_witness_is_gateway_only():
    value = " ".join(sql().split())

    assert (
        "grant execute on function "
        "foundation.shine_ai_attestation_generation_witness_record_v1"
        in value
    )
    assert (
        "grant execute on function "
        "foundation.shine_ai_attestation_generation_witness_current_v1"
        in value
    )
    assert "to foundation_gateway" in value
    assert "from public, anon, authenticated, service_role" in value


def test_edge_exposes_only_bounded_generation_witness_operations():
    value = edge()

    assert "attestation-generation-current" in value
    assert "attestation-generation-record" in value
    assert "shine_ai_attestation_generation_witness_current_v1" in value
    assert "shine_ai_attestation_generation_witness_record_v1" in value
    assert "set local role foundation_gateway" in value
    assert "decrypted_secret" not in value


def test_attestation_generation_witness_binds_response_to_authenticated_client():
    value = " ".join(sql().split())

    assert "'clientid',v_current.client_id" in value
    assert "'clientid','shine.ai.runtime'" in value
    assert "'clientid',v_state.client_id" in value
    assert "client_id text not null" in value
