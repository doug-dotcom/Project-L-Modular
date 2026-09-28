from pathlib import Path


SQL = Path("contracts/foundation/project_l_trace_witness_chain_v1.sql")


def source() -> str:
    return SQL.read_text(encoding="utf-8").lower()


def test_chain_uses_foundation_only_keyed_hmac():
    sql = source()

    assert "project_l_trace_witness_hmac_v1" in sql
    assert "vault.decrypted_secrets" in sql
    assert "shine-ai:decision-trace-trust-state-witness-chain:v1" in sql
    assert "extensions.hmac(" in sql
    assert "previous_chain_tag" in sql
    assert "chain_tag" in sql


def test_existing_history_is_authenticated_before_backfill():
    sql = source()

    assert "witness-chain-backfill-auth-integrity-failed" in sql
    assert (
        "shine-ai:decision-trace-trust-state-monotonic-head-witness:v1"
        in sql
    )
    assert "v_expected_auth_tag<>v_event.auth_tag" in sql
    assert "v_event.client_id<>'shine.companion'" in sql


def test_chain_backfill_requires_contiguous_predecessors():
    sql = source()

    assert "e.sequence=v_event.sequence-1" in sql
    assert "witness-chain-backfill-gap" in sql
    assert "repeat('0',64)" in sql


def test_history_verifier_walks_from_genesis_to_current_head():
    sql = source()

    assert "project_l_trace_witness_verify_history_v1" in sql
    assert "v_expected_sequence bigint := 1" in sql
    assert "order by e.sequence" in sql
    assert "witness-chain-sequence-gap" in sql
    assert "witness-chain-event-auth-failed" in sql
    assert "witness-chain-link-failed" in sql
    assert "witness-chain-auth-failed" in sql
    assert "witness-chain-head-mismatch" in sql


def test_read_path_requires_full_history_verification():
    sql = source()
    current = sql.split(
        "create or replace function foundation."
        "project_l_trace_witness_current_v1"
    )[1].split(
        "create or replace function foundation."
        "project_l_trace_witness_record_v1"
    )[0]

    assert "project_l_trace_witness_verify_history_v1" in current
    assert "coalesce(v_history->>'status','')<>'verified'" in current
    assert "'chainversion',v_state.chain_version" in current
    assert "'chaintag',v_state.chain_tag" in current


def test_write_path_verifies_full_history_before_monotonic_decisions():
    sql = source()
    record = sql.split(
        "create or replace function foundation."
        "project_l_trace_witness_record_v1"
    )[1].split(
        "revoke all on function foundation."
        "project_l_trace_witness_current_v1"
    )[0]

    history = record.index("project_l_trace_witness_verify_history_v1")
    rollback = record.index("witness-sequence-rollback")
    replay = record.index("'replayed',true")

    assert -1 < history < rollback
    assert history < replay


def test_new_events_bind_to_previous_keyed_chain_tag():
    sql = source()
    record = sql.split(
        "create or replace function foundation."
        "project_l_trace_witness_record_v1"
    )[1].split(
        "revoke all on function foundation."
        "project_l_trace_witness_current_v1"
    )[0]

    assert "else v_current.chain_tag" in record
    assert "witness-chain-predecessor-unavailable" in record
    assert "'previouschaintag':'" not in record
    assert '"previouschaintag"' in record
    assert "v_chain_tag := encode(" in record
    assert "chain_version,previous_chain_tag" in record
    assert "chain_tag,witnessed_at" in record


def test_history_verifier_is_not_exposed_to_runtime_roles():
    sql = source()

    assert (
        "revoke all on function foundation."
        "project_l_trace_witness_verify_history_v1(text)"
        in sql
    )
    assert "service_role" in sql
    assert "foundation_gateway" in sql
    assert "shine_defence_runtime" in sql
