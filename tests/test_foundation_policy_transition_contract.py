from pathlib import Path


SQL = Path(
    "contracts/foundation/"
    "project_l_policy_transition_authorization_v1.sql"
)
EDGE = Path(
    "contracts/foundation/project-l-trust-witness/index.ts"
)


def sql_source() -> str:
    return SQL.read_text(encoding="utf-8").lower()


def edge_source() -> str:
    return EDGE.read_text(encoding="utf-8").lower()


def test_foundation_policy_transition_uses_existing_vault_witness_key():
    sql = sql_source()

    assert "project_l_trace_witness_hmac_v1" in sql
    assert "vault.decrypted_secrets" in sql
    assert "foundation-witness-v1" in sql
    assert "vault.create_secret" not in sql


def test_foundation_policy_transition_reauthenticates_current_witness():
    sql = sql_source()
    authorize = sql.split(
        "create or replace function foundation."
        "project_l_policy_transition_authorize_v1"
    )[1].split(
        "create or replace function foundation."
        "project_l_policy_transition_verify_v1"
    )[0]

    assert "project_l_trace_witness_current_v1" in authorize
    assert "foundation-witness-current-unverified" in authorize
    assert "effective_integration_client_credentials" in authorize
    assert "client_id='shine.companion'" in authorize


def test_foundation_policy_transition_matches_layer149_domain_and_fields():
    sql = sql_source()

    assert (
        "shine-ai:decision-trace-trust-state-"
        "witness-quorum-policy-transition:v1"
        in sql
    )
    for field in (
        "authorizationversion",
        "authorizationtype",
        "witnessid",
        "fromgeneration",
        "togeneration",
        "frompolicysha256",
        "topolicysha256",
    ):
        assert field in sql


def test_foundation_policy_transition_requires_one_step_predecessor_and_change():
    sql = sql_source()
    authorize = sql.split(
        "create or replace function foundation."
        "project_l_policy_transition_authorize_v1"
    )[1].split(
        "create or replace function foundation."
        "project_l_policy_transition_verify_v1"
    )[0]

    assert "v_to_generation<>v_from_generation+1" in authorize
    assert "p_next_policy->>'previouspolicysha256'<>v_from_sha" in authorize
    assert "v_to_minimum=v_from_minimum and v_to_ids=v_from_ids" in authorize
    assert "'foundation-project-l'=any(v_from_ids)" in authorize


def test_foundation_authorization_events_are_append_only_and_runtime_roles_blocked():
    sql = sql_source()

    assert "project_l_policy_transition_authorization_events" in sql
    assert "unique(witness_id,from_policy_sha256,to_policy_sha256,auth_key_id)" in sql
    assert "enable row level security" in sql
    assert (
        "revoke all on foundation.project_l_policy_transition_authorization_events"
        in sql
    )
    assert "grant insert" not in sql
    assert "grant update" not in sql


def test_foundation_edge_preserves_witness_api_and_adds_two_transition_operations():
    edge = edge_source()

    assert "project_l_trace_witness_current_v1" in edge
    assert "project_l_trace_witness_record_v1" in edge
    assert "policy-transition-authorize" in edge
    assert "project_l_policy_transition_authorize_v1" in edge
    assert "policy-transition-verify" in edge
    assert "project_l_policy_transition_verify_v1" in edge
    assert "x-shine-client-token" in edge
    assert "decrypted_secret" not in edge
