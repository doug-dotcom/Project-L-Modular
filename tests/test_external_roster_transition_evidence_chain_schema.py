from pathlib import Path

M=Path("supabase/migrations/20260928232500_project_l_layer211_roster_transition_evidence_chain.sql")
def source(): return M.read_text(encoding="utf-8").lower()

def test_evidence_chain_uses_project_l_vault_hmac():
    s=source()
    assert "project_l_external_roster_transition_evidence_chain_hmac_v1" in s
    assert "vault.create_secret" in s
    assert "extensions.hmac" in s

def test_evidence_chain_starts_at_generation_two_zero_anchor():
    s=source()
    assert "v_expected_generation integer := 2" in s
    assert "repeat('0',64)" in s
    assert "external-roster-evidence-chain-backfill-generation-gap" in s

def test_evidence_chain_binds_exact_evidence_and_policy_continuity():
    s=source()
    assert "evidencesha256" in s
    assert "authorizations" in s
    assert "external-roster-transition-evidence-chain-policy-link-mismatch" in s
    assert "external-roster-transition-evidence-chain-evidence-digest-mismatch" in s

def test_evidence_chain_full_verifier_fails_closed():
    s=source()
    assert "external-roster-transition-evidence-chain-generation-gap" in s
    assert "external-roster-transition-evidence-chain-link-mismatch" in s
    assert "external-roster-transition-evidence-chain-auth-failed" in s

def test_evidence_chain_verifier_is_rpc_only():
    s=source()
    assert "shine_ai_external_roster_transition_evidence_chain_verify_v1" in s
    assert "from public, anon, authenticated" in s
    assert "to service_role" in s
