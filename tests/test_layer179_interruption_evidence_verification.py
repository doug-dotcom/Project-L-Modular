"""Layer 179 — recovery verifies interruption evidence against row facts."""

import re

from core.cognition.durable_tasks import verify_interruption_evidence


EVIDENCE = {
    "version": "1.0",
    "reason": "lease_expired",
    "interrupted_at": "2026-09-26T11:36:08+00:00",
    "lease_until": "2026-09-26T11:32:08+00:00",
    "checkpoint": "connected_action_recorded",
    "worker_id": "20000000-0000-4000-8000-000000001799",
    "claim_token": "30000000-0000-4000-8000-000000001799",
    "action_journalled": True,
}


def row(**changes):
    value = {
        "status": "interrupted",
        "lease_until": EVIDENCE["lease_until"],
        "checkpoint": EVIDENCE["checkpoint"],
        "action_receipt": {"status": "confirmed"},
        "interruption_evidence": dict(EVIDENCE),
    }
    value.update(changes)
    return value


def test_valid_interruption_evidence_matches_recovered_row():
    check = verify_interruption_evidence(row())
    assert check["valid"] is True
    assert check["status"] == "verified"


def test_missing_persisted_interruption_evidence_fails_closed():
    check = verify_interruption_evidence(row(interruption_evidence=None))
    assert check["valid"] is False
    assert "interruption_evidence_missing" in check["issues"]


def test_checkpoint_or_lease_mismatch_fails_closed():
    assert verify_interruption_evidence(row(checkpoint="different"))["valid"] is False
    assert verify_interruption_evidence(row(lease_until="different"))["valid"] is False


def test_action_journal_presence_must_match_evidence():
    check = verify_interruption_evidence(row(action_receipt=None))
    assert check["valid"] is False
    assert "interruption_evidence_journal_mismatch" in check["issues"]


def test_evidence_on_noninterrupted_task_is_rejected():
    check = verify_interruption_evidence(row(status="ready"))
    assert check["valid"] is False
    assert "interruption_evidence_on_noninterrupted_task" in check["issues"]


def test_read_time_expiry_is_explicitly_pending_reaper():
    source = open("core/cognition/durable_tasks.py", encoding="utf-8").read()
    assert "'status': 'pending_reaper'" in source
    assert "'pending': True" in source


def test_layer179_release_marker_is_continuous():
    source=open("api/server.py",encoding="utf-8").read()
    layers=[int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)',source)]
    assert len(layers)==3 and len(set(layers))==1 and layers[0]>=179
