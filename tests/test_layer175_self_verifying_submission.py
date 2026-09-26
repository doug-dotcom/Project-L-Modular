"""Layer 175 — verified and acknowledgement-safe durable submission."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core.cognition.durable_tasks import (
    TaskStore,
    owner_identity,
    request_hash,
    submission_proof,
)


REQUEST_ID = "10000000-0000-4000-8000-000000001756"
REQUEST = {
    "message": "Hello 👊",
    "request_id": REQUEST_ID,
    "conversation_id": None,
}
RECOVERY_TOKEN = "x" * 64
KNOWN_PROOF = "68a9aff9b20d9bd6b854f585015259e4da5a23b30e97e15ad5e66800f337e85c"


class SubmitClient:
    def __init__(
        self,
        submit_result=None,
        submit_error=None,
        confirm_result=None,
        confirm_error=None,
    ):
        self.submit_result = submit_result
        self.submit_error = submit_error
        self.confirm_result = confirm_result
        self.confirm_error = confirm_error
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))

        def execute():
            if name == "l_task_submit_verified":
                if self.submit_error is not None:
                    raise self.submit_error
                return SimpleNamespace(data=self.submit_result)
            if name == "l_task_confirm_submit":
                if self.confirm_error is not None:
                    raise self.confirm_error
                return SimpleNamespace(data=self.confirm_result)
            raise AssertionError(f"unexpected rpc {name}")

        return SimpleNamespace(execute=execute)


def test_cross_language_submission_proof_has_known_unicode_vector():
    assert submission_proof(REQUEST) == KNOWN_PROOF


def test_verified_submit_sends_full_hash_and_independent_proof():
    client = SubmitClient(
        submit_result={"status": "queued", "request_id": REQUEST_ID}
    )
    store = TaskStore(client)

    result = store.submit(REQUEST, RECOVERY_TOKEN)

    assert result["status"] == "queued"
    assert len(client.calls) == 1
    name, params = client.calls[0]
    assert name == "l_task_submit_verified"
    assert params["p_hash"] == request_hash(REQUEST)
    assert params["p_proof"] == KNOWN_PROOF
    assert params["p_request"] == REQUEST
    assert params["p_user"] == owner_identity(RECOVERY_TOKEN)[0]
    assert params["p_owner"] == owner_identity(RECOVERY_TOKEN)[1]


def test_lost_submit_ack_is_reconciled_read_only_without_resubmit():
    client = SubmitClient(
        submit_error=ConnectionError("synthetic lost acknowledgement"),
        confirm_result={"status": "queued", "request_id": REQUEST_ID},
    )

    result = TaskStore(client).submit(REQUEST, RECOVERY_TOKEN)

    assert result == {"status": "queued", "request_id": REQUEST_ID}
    assert [name for name, _ in client.calls] == [
        "l_task_submit_verified",
        "l_task_confirm_submit",
    ]


def test_reconciliation_miss_fails_without_second_submit():
    client = SubmitClient(
        submit_error=ConnectionError("synthetic lost acknowledgement"),
        confirm_result={"status": "not_found"},
    )

    with pytest.raises(RuntimeError, match="acknowledgement unavailable"):
        TaskStore(client).submit(REQUEST, RECOVERY_TOKEN)

    assert [name for name, _ in client.calls] == [
        "l_task_submit_verified",
        "l_task_confirm_submit",
    ]


def test_reconciliation_transport_failure_stays_private():
    client = SubmitClient(
        submit_error=ConnectionError("private submit detail"),
        confirm_error=ConnectionError("private confirm detail"),
    )

    with pytest.raises(RuntimeError) as exc:
        TaskStore(client).submit(REQUEST, RECOVERY_TOKEN)

    assert "private submit detail" not in str(exc.value)
    assert "private confirm detail" not in str(exc.value)


def test_chat_start_maps_invalid_verified_submission_to_400(monkeypatch):
    from api import server

    monkeypatch.setattr(
        server,
        "task_store",
        SimpleNamespace(submit=lambda *_args: {"status": "invalid"}),
    )
    with pytest.raises(HTTPException) as exc:
        server.start_chat(
            server.ChatRequest(message="test", request_id=REQUEST_ID),
            RECOVERY_TOKEN,
        )

    assert exc.value.status_code == 400


def test_runtime_no_longer_calls_legacy_submit_rpc():
    source = Path("core/cognition/durable_tasks.py").read_text(encoding="utf-8")
    assert "self.rpc('l_task_submit'," not in source
    assert "self.rpc('l_task_submit_verified'," in source
    assert "self.rpc('l_task_confirm_submit'," in source


def test_reconciliation_migration_is_read_only_and_backend_only():
    source = Path(
        "supabase/migrations/"
        "20260926081409_project_l_layer175_reconcile_submit_ack.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create or replace function public.l_task_confirm_submit" in source
    assert "language sql" in source
    assert "security invoker" in source
    assert "stable" in source
    assert "update public.l_chat_tasks" not in source
    assert "insert into public.l_chat_tasks" not in source
    assert "from public, anon, authenticated" in source
    assert "to service_role;" in source


def test_verified_submit_cutover_uses_cross_language_proof_and_retires_legacy():
    source = Path(
        "supabase/migrations/"
        "20260926081814_project_l_layer175_verified_submit_cutover.sql"
    ).read_text(encoding="utf-8")

    assert "create or replace function public.l_task_submit_verified" in source
    assert "layer175-submit-v1|" in source
    assert "octet_length" in source
    assert "p_proof" in source
    assert (
        "revoke execute on function "
        "public.l_task_submit(uuid,uuid,text,text,jsonb)"
        in source
    )
    assert "from service_role;" in source


def test_initial_jsonb_text_hash_is_superseded_by_verified_cutover():
    initial = Path(
        "supabase/migrations/"
        "20260926081725_project_l_layer175_self_verifying_submission.sql"
    ).read_text(encoding="utf-8")
    cutover = Path(
        "supabase/migrations/"
        "20260926081814_project_l_layer175_verified_submit_cutover.sql"
    ).read_text(encoding="utf-8")

    assert "convert_to(p_request::text,'UTF8')" in initial
    assert "l_task_submit_verified" in cutover
    assert "layer175-submit-v1|" in cutover


def test_layer175_release_marker_is_continuous():
    source = Path("api/server.py").read_text(encoding="utf-8")
    layers = [
        int(v)
        for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 175
