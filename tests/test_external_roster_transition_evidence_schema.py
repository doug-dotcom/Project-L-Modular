from pathlib import Path

M=Path("supabase/migrations/20260928224000_project_l_layer208_roster_transition_evidence.sql")
def source(): return M.read_text(encoding="utf-8").lower()

def test_evidence_is_bound_to_committed_roster_ledger():
    s=source()
    assert "external-roster-transition-evidence-ledger-mismatch" in s
    assert "acceptance_mode<>'previous-roster-quorum'" in s

def test_evidence_envelopes_bind_generations_and_digests():
    s=source()
    assert "fromgeneration" in s
    assert "togeneration" in s
    assert "frompolicysha256" in s
    assert "topolicysha256" in s
    assert "external-roster-transition-evidence-envelope-mismatch" in s

def test_evidence_is_immutable_per_generation():
    s=source()
    assert "external-roster-transition-evidence-equivocation" in s
    assert "'mode','existing'" in s

def test_evidence_table_has_no_direct_service_role_access():
    s=source()
    assert "from public, anon, authenticated, service_role" in s
    assert "to service_role" in s
