from pathlib import Path


SQL = Path("contracts/foundation/project_l_trace_witness_v1.sql")
EDGE = Path(
    "contracts/foundation/project-l-trust-witness/index.ts"
)


def sql_source() -> str:
    return SQL.read_text(encoding="utf-8").lower()


def edge_source() -> str:
    return EDGE.read_text(encoding="utf-8").lower()


def test_foundation_witness_secret_stays_in_vault():
    sql = sql_source()

    assert "vault.create_secret" in sql
    assert "project_l_trace_witness_hmac_v1" in sql
    assert "vault.decrypted_secrets" in sql
    assert "decrypted_secret" in sql


def test_foundation_witness_reuses_registered_companion_identity():
    sql = sql_source()

    assert "effective_integration_client_credentials" in sql
    assert "client_id='shine.companion'" in sql
    assert "effective_status='active'" in sql
    assert "extensions.digest(p_client_token,'sha256')" in sql


def test_foundation_witness_is_monotonic_and_append_only():
    sql = sql_source()

    assert "witness-sequence-rollback" in sql
    assert "witness-sequence-equivocation" in sql
    assert "witness-sequence-skip" in sql
    assert "witness-generation-invalid" in sql
    assert "witness-keyset-equivocation" in sql
    assert "witness-state-not-advanced" in sql
    assert "project_l_trace_witness_events" in sql
    assert "unique (witness_id, sequence)" in sql
    assert "pg_advisory_xact_lock" in sql


def test_foundation_runtime_roles_cannot_write_witness_tables_directly():
    sql = sql_source()

    assert (
        "revoke all on foundation.project_l_trace_witness_state"
        in sql
    )
    assert (
        "revoke all on foundation.project_l_trace_witness_events"
        in sql
    )
    assert "grant execute on function foundation.project_l_trace_witness" in sql
    assert "to foundation_gateway" in sql


def test_witness_hmac_uses_layer146_domain_and_bounded_material():
    sql = sql_source()

    assert (
        "shine-ai:decision-trace-trust-state-monotonic-head-witness:v1"
        in sql
    )
    for field in (
        "witnessversion",
        "witnesstype",
        "witnessid",
        "headversion",
        "sequence",
        "headsha256",
        "generation",
        "keyset_sha256",
        "statesha256",
    ):
        assert field in sql


def test_edge_uses_custom_service_auth_and_never_reads_witness_secret():
    edge = edge_source()

    assert "x-shine-client-token" in edge
    assert "project_l_trace_witness_current_v1" in edge
    assert "project_l_trace_witness_record_v1" in edge
    assert "set local role foundation_gateway" in edge
    assert "decrypted_secret" not in edge
    assert "project_l_trace_witness_hmac_v1" not in edge
