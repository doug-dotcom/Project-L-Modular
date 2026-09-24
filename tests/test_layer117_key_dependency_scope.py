"""An owner scan cannot retire shared keys or ignore damaged dependencies."""

from copy import deepcopy
from datetime import datetime, timezone
import json

import httpx
import pytest
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from core.cognition import key_retirement_certification as keys
from core.cognition import durable_task_ledger_audit as ledger
from core.cognition.answer_authenticity import LEGACY_VERSION, VERSION as KEYRING_VERSION
from tests.test_layer109_key_retirement_certification import (
    K2_ID, K3_ID, LEGACY_KEY_LABEL, candidate, install_env, row,
    runtime_env, signed_result,
)
from tests.test_layer113_stable_ledger_scan import MovingLedger, NOW, TOKEN


RID = "00000000-0000-4000-8000-000000000116"


@pytest.fixture(autouse=True)
def keyring(monkeypatch):
    install_env(monkeypatch, runtime_env())


def report(rows, **kwargs):
    return keys.summarise_key_dependencies(
        rows, scan_complete=kwargs.get("complete", True), capped=kwargs.get("capped", False),
        configured_status=kwargs.get("configured_status"),
    )


def test_empty_owner_history_never_qualifies_shared_keys_for_retirement():
    result = report([])
    assert result["dependency_assessment_complete"]
    assert candidate(result, K3_ID)["decision"] == "no_references_in_owner_scope"
    assert candidate(result, LEGACY_KEY_LABEL)["decision"] == "no_references_in_owner_scope"
    assert not any(c["retirement_eligible"] for c in result["retirement_candidates"])
    assert not result["claims"]["global_key_dependencies_verified"]
    assert result["policy"]["global_dependency_check_required"]
    assert not result["policy"]["owner_scope_can_authorise_retirement"]


@pytest.mark.parametrize("bad_id", [None, "", "private-invalid-id", []])
def test_corrupt_request_id_does_not_erase_known_key_reference(bad_id):
    item = row(bad_id, signed_result(RID, signing_active=K3_ID))
    result = report([item])
    assert candidate(result, K3_ID)["decision"] == "in_use"
    assert result["stored_key_references"][K3_ID] == 1
    assert result["malformed_rows"] == 1 and result["uncertain_rows"] == 1
    assert not result["dependency_assessment_complete"]
    assert candidate(result, LEGACY_KEY_LABEL)["decision"] == "unknown_unassessed_records"
    assert "private-invalid-id" not in json.dumps(result)


@pytest.mark.parametrize("item", [None, "private row", {}, []])
def test_malformed_records_block_clean_dependency_assessment(item):
    result = report([item])
    assert result["status"] == "complete_with_uncertainty"
    assert result["scan_complete"]
    assert result["uncertain_rows"] == 1
    assert result["claims"]["key_dependency_coverage"] == "unverified"
    assert candidate(result, K3_ID)["decision"] == "unknown_unassessed_records"


@pytest.mark.parametrize("auth", [None, [], {}, "private receipt", {
    "version": KEYRING_VERSION, "key_id": "private unknown key",
}, {"version": "private version", "key_id": K3_ID}])
def test_unknown_or_malformed_receipts_are_counted_without_exposing_labels(auth):
    payload = {"reply": "private answer", "cognition": {"answer_authenticity": auth}}
    result = report([row(RID, payload)])
    assert result["stored_key_references"][keys.UNKNOWN_REFERENCE] == 1
    assert result["uncertain_rows"] == 1
    assert "private" not in json.dumps(result)
    assert RID not in json.dumps(result)
    assert not result["dependency_assessment_complete"]


def test_malformed_cognition_cannot_masquerade_as_unsigned_legacy():
    result = report([row(RID, {"reply": "private", "cognition": "private malformed data"})])
    assert result["uncertain_rows"] == 1
    assert result["stored_key_references"][keys.UNKNOWN_REFERENCE] == 1
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("status", ["ready", "failed"])
def test_missing_terminal_result_keeps_dependency_assessment_unresolved(status):
    result = report([row(RID, None, status)])
    assert result["uncertain_rows"] == 1
    assert candidate(result, K3_ID)["decision"] == "unknown_unassessed_records"
    assert result["ready_without_result"] == int(status == "ready")


def test_legacy_key_in_signing_use_is_protected_even_with_no_stored_answers():
    configured = {"active_key_id": "", "retained_key_ids": [],
                  "legacy_verification_configured": True, "mode": "legacy_single_key"}
    result = report([], configured_status=configured)
    assert candidate(result, LEGACY_KEY_LABEL)["decision"] == "active_do_not_retire"


def test_conflicting_legacy_receipt_keeps_both_visible_dependencies():
    result = report([row(RID, {"reply": "private", "cognition": {"answer_authenticity": {
        "version": LEGACY_VERSION, "key_id": K3_ID,
    }}})])
    assert result["stored_key_references"][LEGACY_KEY_LABEL] == 1
    assert result["stored_key_references"][K3_ID] == 1
    assert candidate(result, LEGACY_KEY_LABEL)["decision"] == "in_use"
    assert result["uncertain_rows"] == 1


def test_invalid_signature_protects_referenced_key_and_blocks_other_zero_claims():
    payload = signed_result(RID, signing_active=K3_ID)
    payload["reply"] = "private changed answer"
    result = report([row(RID, payload)])
    assert candidate(result, K3_ID)["decision"] == "in_use"
    assert candidate(result, LEGACY_KEY_LABEL)["decision"] == "unknown_unassessed_records"
    assert result["unverified_answer_rows"] == 1


def test_verifier_exception_keeps_dependency_counts_and_scans_remaining_records(monkeypatch):
    real = keys.verify_recovered_answer_payload
    calls = []
    def verify(payload, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("private exception detail")
        return real(payload, **kwargs)
    monkeypatch.setattr(keys, "verify_recovered_answer_payload", verify)
    result = report([row(RID, signed_result(RID, signing_active=K3_ID))] * 2)
    assert len(calls) == 2
    assert result["stored_key_references"][K3_ID] == 2
    assert result["verification_error_rows"] == 1
    assert result["uncertain_rows"] == 1
    assert "private" not in json.dumps(result)


def test_caps_take_precedence_but_known_references_stay_protected():
    result = report([row(RID, signed_result(RID, signing_active=K3_ID)), None], complete=False, capped=True)
    assert result["status"] == "incomplete"
    assert candidate(result, K3_ID)["decision"] == "in_use"
    assert candidate(result, LEGACY_KEY_LABEL)["decision"] == "unknown_incomplete_scan"
    assert candidate(result, K2_ID)["decision"] == "active_do_not_retire"


def test_valid_legacy_unsigned_answer_does_not_create_a_spurious_key_dependency():
    items = [row(RID, {"reply": "private old answer"})]
    before = deepcopy(items)
    result = report(items)
    assert result["dependency_assessment_complete"]
    assert result["stored_key_references"] == {}
    assert items == before


def test_key_dependency_loader_does_not_skip_reference_after_concurrent_deletion(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return NOW
    monkeypatch.setattr(ledger, "datetime", Clock)
    ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(1, 5)]
    items = [row(rid, signed_result(rid, signing_active=K3_ID if i == 2 else K2_ID))
             for i, rid in enumerate(ids)]
    def delete_earlier(service, page):
        if page == 2: service.rows.pop(0)
    service = MovingLedger(items, on_page=delete_earlier)
    with httpx.Client(transport=httpx.MockTransport(service)) as transport:
        client = create_client("https://example.supabase.co", "fixture-key", options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        result = keys.load_key_retirement_certification(client, TOKEN, page_size=2)
    assert result["answers_observed"] == 4
    assert result["scan"]["pagination"] == "created_at_request_id_keyset"
    assert result["scan"]["read_only"]
    assert not result["scan"]["transactional_snapshot"]
    assert candidate(result, K3_ID)["decision"] == "in_use"
    assert len(service.requests) == 3
