"""Layer 178 — interrupted tasks carry immutable forensic evidence."""

import re
from pathlib import Path


def test_reaper_records_forensic_interruption_evidence_once():
    source=Path(
        "supabase/migrations/20260926113558_project_l_layer178_interruption_evidence.sql"
    ).read_text(encoding="utf-8").lower()
    for field in [
        "'reason','lease_expired'",
        "'interrupted_at',now()",
        "'lease_until',t.lease_until",
        "'checkpoint',t.checkpoint",
        "'worker_id',t.worker_id",
        "'claim_token',t.claim_token",
        "'action_journalled',(t.action_receipt is not null)",
    ]:
        assert field in source
    assert "t.interruption_evidence is null" in source
    assert "for update skip locked" in source


def test_interruption_does_not_destroy_checkpoint_or_action_journal():
    source=Path(
        "supabase/migrations/20260926113558_project_l_layer178_interruption_evidence.sql"
    ).read_text(encoding="utf-8").lower()
    update=source[source.index("update public.l_chat_tasks as t"):]
    set_clause=update[update.index("set "):update.index("from expired")]
    assert "checkpoint =" not in set_clause
    assert "action_receipt =" not in set_clause


def test_owner_bound_recovery_projects_interruption_evidence():
    source=Path(
        "supabase/migrations/20260926113630_project_l_layer178_recovery_evidence_projection_v2.sql"
    ).read_text(encoding="utf-8").lower()
    assert "interruption_evidence jsonb" in source
    assert "t.interruption_evidence" in source
    assert "security invoker" in source
    assert "stable" in source
    assert "to service_role;" in source


def test_layer178_release_marker_is_continuous():
    source=Path("api/server.py").read_text(encoding="utf-8")
    layers=[int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)',source)]
    assert len(layers)==3 and len(set(layers))==1 and layers[0]>=178
