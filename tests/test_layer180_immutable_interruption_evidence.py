"""Layer 180 — interruption evidence is immutable in Postgres."""

import re
from pathlib import Path


def test_layer180_trigger_makes_recorded_evidence_immutable():
    source=Path(
        "supabase/migrations/20260926120744_project_l_layer180_immutable_interruption_evidence.sql"
    ).read_text(encoding="utf-8").lower()
    assert "old.interruption_evidence is not null" in source
    assert "new.interruption_evidence is distinct from old.interruption_evidence" in source
    assert "errcode = '23514'" in source


def test_layer180_only_allows_valid_running_to_interrupted_creation():
    source=Path(
        "supabase/migrations/20260926120744_project_l_layer180_immutable_interruption_evidence.sql"
    ).read_text(encoding="utf-8").lower()
    assert "old.status <> 'running'" in source
    assert "new.status <> 'interrupted'" in source
    assert "reason' <> 'lease_expired'" in source
    assert "checkpoint' is distinct from old.checkpoint" in source
    assert "worker_id' is distinct from old.worker_id::text" in source
    assert "claim_token' is distinct from old.claim_token::text" in source
    assert "(old.action_receipt is not null)::text" in source


def test_layer180_trigger_function_is_not_directly_executable():
    source=Path(
        "supabase/migrations/20260926120744_project_l_layer180_immutable_interruption_evidence.sql"
    ).read_text(encoding="utf-8").lower()
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "from public, anon, authenticated, service_role;" in source


def test_layer180_release_marker_is_continuous():
    source=Path("api/server.py").read_text(encoding="utf-8")
    layers=[int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)',source)]
    assert len(layers)==3 and len(set(layers))==1 and layers[0]>=180
