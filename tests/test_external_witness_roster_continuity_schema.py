from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/"
    "20260928222000_project_l_layer207_external_roster_continuity.sql"
)

def source():
    return MIGRATION.read_text(encoding="utf-8").lower()

def test_roster_advance_is_exactly_next_generation():
    sql=source()
    assert "p_next_generation<>v_current.generation+1" in sql
    assert "p_next_previous_policy_sha256<>v_current.policy_sha256" in sql

def test_roster_advance_requires_previous_roster_threshold():
    sql=source()
    assert "not (x.witness_id=any(v_current.accepted_witness_ids))" in sql
    assert "v_distinct_auth_count<v_current.minimum_witnesses" in sql
    assert "external-witness-roster-transition-authorizations-insufficient" in sql

def test_roster_advance_records_authorization_evidence():
    sql=source()
    assert "authorizing_witness_ids" in sql
    assert "authorization_sha256" in sql
    assert "'previous-roster-quorum'" in sql

def test_roster_advance_is_service_role_only():
    sql=source()
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
