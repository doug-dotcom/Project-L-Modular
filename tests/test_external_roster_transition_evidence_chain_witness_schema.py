from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928233500_project_l_layer212_evidence_chain_previous_head.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer212_chain_verifier_surfaces_immediate_predecessor_head():
    sql = source()

    assert (
        "v_latest_previous_chain_tag text := null"
        in sql
    )
    assert (
        "v_latest_previous_chain_tag := v_previous_chain_tag"
        in sql
    )
    assert "'latestpreviouschaintag',v_latest_previous_chain_tag" in sql


def test_layer212_predecessor_is_captured_before_head_advances():
    sql = source()

    predecessor = sql.index(
        "v_latest_previous_chain_tag := v_previous_chain_tag"
    )
    advance = sql.index(
        "v_previous_chain_tag := v_row.chain_tag"
    )
    assert predecessor < advance


def test_layer212_chain_verification_still_recomputes_hmac_and_evidence():
    sql = source()

    assert "external-roster-transition-evidence-chain-evidence-digest-mismatch" in sql
    assert "external-roster-transition-evidence-chain-auth-failed" in sql
    assert "extensions.hmac(" in sql
    assert "extensions.digest(" in sql


def test_layer212_function_remains_service_role_only():
    sql = source()

    assert (
        "revoke all on function"
        " public.shine_ai_external_roster_transition_evidence_chain_verify_v1()"
        in sql
    )
    assert "from public, anon, authenticated" in sql
    assert (
        "grant execute on function"
        " public.shine_ai_external_roster_transition_evidence_chain_verify_v1()"
        in sql
    )
    assert "to service_role" in sql
