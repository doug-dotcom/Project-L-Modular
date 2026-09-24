"""Layer 109: exhaustive signing-key dependency certification."""

from types import SimpleNamespace as NS

import pytest

from core.cognition.answer_authenticity import (
    ACTIVE_KEY_ID_ENV,
    KEY_ENV_PREFIX,
    SIGNING_KEY_ENV,
    VERIFY_KEY_IDS_ENV,
    sign_answer_provenance,
)
from core.cognition.answer_provenance import build_answer_provenance
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.key_retirement_certification import (
    LEGACY_KEY_LABEL,
    VERSION,
    load_key_retirement_certification,
    summarise_key_dependencies,
)
from core.cognition.recovery_provenance import (
    PROTOCOL_VERSION,
    mark_answer_provenance_required,
)
from core.cognition.release_provenance import build_release_provenance


TOKEN = "x" * 64
REPLY = "PRIVATE KEY-RETIREMENT TEST ANSWER"
COMMIT = "9" * 40
LEGACY_KEY = "L" * 64
K2_ID = "k2-2026-09"
K3_ID = "k3-2026-10"
K2 = "2" * 64
K3 = "3" * 64


def key_env_name(key_id):
    return KEY_ENV_PREFIX + key_id.upper().replace("-", "_")


def runtime_env(active=K2_ID, verify=f"{K2_ID},{K3_ID}"):
    return {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        SIGNING_KEY_ENV: LEGACY_KEY,
        ACTIVE_KEY_ID_ENV: active,
        VERIFY_KEY_IDS_ENV: verify,
        key_env_name(K2_ID): K2,
        key_env_name(K3_ID): K3,
    }


def install_env(monkeypatch, env):
    names = set(runtime_env()) | {
        SIGNING_KEY_ENV,
        ACTIVE_KEY_ID_ENV,
        VERIFY_KEY_IDS_ENV,
        key_env_name(K2_ID),
        key_env_name(K3_ID),
    }
    for name in names:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def signed_result(request_id, *, signing_active=K2_ID, legacy=False):
    env = runtime_env(active=signing_active)
    release = build_release_provenance(env)
    model = {"status": "complete", "model_id": "fixture-model"}
    context = {"version": "1.0", "mode": "lean", "rendered_chars": 500}
    persistence = {"version": "1.0", "status": "verified", "valid": True}
    answer = build_answer_provenance(
        request_id=request_id,
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
        release_layer=109,
    )
    auth = (
        sign_answer_provenance(answer, signing_key=LEGACY_KEY)
        if legacy
        else sign_answer_provenance(answer, environ=env)
    )
    body = {
        "reply": REPLY,
        "server": "vx",
        "cognition": {
            "release_provenance": release,
            "answer_provenance": answer,
            "answer_authenticity": auth,
            "model_receipt": model,
            "context_budget": context,
            "assistant_persistence": persistence,
        },
    }
    body = mark_answer_provenance_required(
        body,
        protocol_version=PROTOCOL_VERSION,
    )
    return seal_chat_delivery_payload(body, request_id=request_id)


def row(request_id, result, status="ready"):
    return {
        "request_id": request_id,
        "created_at": "2026-09-24T00:00:00+00:00",
        "status": status,
        "result": result,
    }


def candidate(report, key_id):
    return next(
        item for item in report["retirement_candidates"]
        if item["key_id"] == key_id
    )


def test_complete_scan_protects_active_and_identifies_zero_reference_inactive_key(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    rows = [
        row("00000000-0000-4000-8000-000000000201", signed_result(
            "00000000-0000-4000-8000-000000000201",
            signing_active=K2_ID,
        )),
    ]
    report = summarise_key_dependencies(
        rows,
        scan_complete=True,
        capped=False,
    )

    assert report["version"] == VERSION
    assert report["status"] == "complete"
    assert report["scan_complete"] is True
    assert report["stored_key_references"][K2_ID] == 1

    k2 = candidate(report, K2_ID)
    k3 = candidate(report, K3_ID)
    legacy = candidate(report, LEGACY_KEY_LABEL)

    assert k2["decision"] == "active_do_not_retire"
    assert k2["stored_references"] == 1
    assert k3["decision"] == "eligible_for_operator_review"
    assert k3["stored_references"] == 0
    assert legacy["decision"] == "eligible_for_operator_review"
    assert report["policy"]["automatic_retirement"] is False
    assert report["claims"]["safe_to_auto_retire_any_key"] is False


def test_inactive_key_with_any_reference_is_in_use(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    request_id = "00000000-0000-4000-8000-000000000202"
    rows = [row(request_id, signed_result(request_id, signing_active=K3_ID))]
    report = summarise_key_dependencies(
        rows,
        scan_complete=True,
        capped=False,
    )

    k3 = candidate(report, K3_ID)
    assert k3["stored_references"] == 1
    assert k3["decision"] == "in_use"


def test_layer104_legacy_signature_dependency_blocks_legacy_retirement(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    request_id = "00000000-0000-4000-8000-000000000203"
    report = summarise_key_dependencies(
        [row(request_id, signed_result(request_id, legacy=True))],
        scan_complete=True,
        capped=False,
    )

    assert report["stored_key_references"][LEGACY_KEY_LABEL] == 1
    legacy = candidate(report, LEGACY_KEY_LABEL)
    assert legacy["stored_references"] == 1
    assert legacy["decision"] == "in_use"


def test_tampered_invalid_record_still_counts_raw_key_dependency(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    request_id = "00000000-0000-4000-8000-000000000204"
    payload = signed_result(request_id, signing_active=K3_ID)
    body = dict(payload)
    body.pop("delivery_receipt")
    cognition = dict(body["cognition"])
    auth = dict(cognition["answer_authenticity"])
    auth["signature"] = "0" * 64
    cognition["answer_authenticity"] = auth
    body["cognition"] = cognition
    tampered = seal_chat_delivery_payload(body, request_id=request_id)

    report = summarise_key_dependencies(
        [row(request_id, tampered)],
        scan_complete=True,
        capped=False,
    )

    assert report["stored_key_references"][K3_ID] == 1
    assert candidate(report, K3_ID)["decision"] == "in_use"
    assert report["verification_states"]["invalid"] == 1
    assert report["issue_codes"]["answer_authenticity_signature_mismatch"] == 1


def test_incomplete_or_capped_scan_never_grants_zero_reference_eligibility(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    report = summarise_key_dependencies(
        [],
        scan_complete=False,
        capped=True,
    )

    assert report["status"] == "incomplete"
    assert report["scan_complete"] is False
    assert candidate(report, K3_ID)["decision"] == "unknown_incomplete_scan"
    assert candidate(report, LEGACY_KEY_LABEL)["decision"] == "unknown_incomplete_scan"


def test_report_never_returns_answer_text_request_ids_or_secrets(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)
    request_id = "00000000-0000-4000-8000-000000000205"

    report = summarise_key_dependencies(
        [row(request_id, signed_result(request_id, signing_active=K2_ID))],
        scan_complete=True,
        capped=False,
    )
    text = str(report)

    assert REPLY not in text
    assert request_id not in text
    assert K2 not in text
    assert K3 not in text
    assert LEGACY_KEY not in text
    assert report["privacy"]["answer_text_returned"] is False
    assert report["privacy"]["raw_request_ids_returned"] is False
    assert report["privacy"]["secret_values_returned"] is False


class Query:
    def __init__(self, rows, calls):
        self.rows = rows
        self.calls = calls
        self.start = 0
        self.end = len(rows) - 1

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.calls.append(("order", column, desc))
        return self

    def range(self, start, end):
        self.calls.append(("range", start, end))
        self.start, self.end = start, end
        return self

    def execute(self):
        return NS(data=self.rows[self.start:self.end + 1])


class Client:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return Query(self.rows, self.calls)


def test_loader_pages_entire_owner_history_and_is_read_only(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    rows = []
    for index in range(7):
        request_id = f"00000000-0000-4000-8000-{300 + index:012d}"
        rows.append(row(
            request_id,
            signed_result(request_id, signing_active=K2_ID),
        ))

    client = Client(rows)
    report = load_key_retirement_certification(
        client,
        TOKEN,
        page_size=3,
        max_rows=20,
    )

    assert report["scan_complete"] is True
    assert report["capped"] is False
    assert report["answers_observed"] == 7
    assert report["scan"]["pages_read"] == 3
    assert report["scan"]["rows_read"] == 7
    assert report["scan"]["read_only"] is True
    assert ("table", "l_chat_tasks") in client.calls
    assert any(call[0] == "eq" and call[1] == "user_id" for call in client.calls)
    assert any(call[0] == "eq" and call[1] == "owner_hash" for call in client.calls)
    assert ("order", "created_at", False) in client.calls
    assert ("range", 0, 2) in client.calls
    assert ("range", 3, 5) in client.calls
    assert ("range", 6, 8) in client.calls
    assert not any(
        call[0] in {"insert", "update", "delete", "upsert", "rpc"}
        for call in client.calls
    )


def test_loader_marks_scan_incomplete_when_safety_cap_is_hit(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    rows = []
    for index in range(6):
        request_id = f"00000000-0000-4000-8000-{400 + index:012d}"
        rows.append(row(request_id, signed_result(request_id)))

    report = load_key_retirement_certification(
        Client(rows),
        TOKEN,
        page_size=2,
        max_rows=4,
    )

    assert report["scan_complete"] is False
    assert report["capped"] is True
    assert report["scan"]["rows_read"] == 4
    assert report["scan"]["max_rows"] == 4
    assert candidate(report, K3_ID)["decision"] == "unknown_incomplete_scan"


@pytest.mark.parametrize(
    "page_size,max_rows",
    [(0, 100), (101, 100), (1.5, 100), (10, 0), (10, 10001), (10, "100")],
)
def test_loader_rejects_invalid_scan_bounds(page_size, max_rows):
    with pytest.raises(ValueError):
        load_key_retirement_certification(
            Client([]),
            TOKEN,
            page_size=page_size,
            max_rows=max_rows,
        )


def test_server_endpoint_exposes_read_only_retirement_certificate(monkeypatch):
    from api import server

    env = runtime_env()
    install_env(monkeypatch, env)
    request_id = "00000000-0000-4000-8000-000000000206"
    client = Client([row(request_id, signed_result(request_id))])
    monkeypatch.setattr(server.task_store, "client", client)

    report = server.cognition_key_retirement_certification(
        page_size=50,
        max_rows=1000,
        x_l_recovery_token=TOKEN,
    )

    assert report["mode"] == "signing_key_dependency_certification"
    assert report["scan_complete"] is True
    assert report["policy"]["automatic_retirement"] is False
    assert report["scan"]["scope"] == "recovery_token_owner_all_saved_tasks"


def test_server_surfaces_layer109_key_retirement_readiness():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"key_retirement_certification_ready": True' in source
    assert '@app.get("/cognition/key-retirement-certification")' in source
    assert "load_key_retirement_certification(" in source
