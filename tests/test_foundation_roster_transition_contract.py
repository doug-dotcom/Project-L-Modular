from pathlib import Path

SQL=Path("contracts/foundation/project_l_external_roster_transition_authorization_v1.sql")

def source():
    return SQL.read_text(encoding="utf-8").lower()

def test_foundation_roster_authorization_requires_healthy_witness():
    sql=source()
    assert "project_l_trace_witness_current_v1" in sql
    assert "foundation-roster-transition-witness-unverified" in sql

def test_foundation_roster_authorization_requires_previous_membership():
    sql=source()
    assert '["foundation-project-l"]' in sql
    assert "foundation-roster-transition-invalid" in sql

def test_foundation_roster_authorization_binds_transition():
    sql=source()
    assert "external-witness-roster-transition-authorization:v1" in sql
    assert "frompolicysha256" in sql
    assert "topolicysha256" in sql
    assert "extensions.hmac" in sql

def test_foundation_roster_authorization_gateway_only():
    sql=source()
    assert "to foundation_gateway" in sql
    assert "shine_defence_runtime" in sql
