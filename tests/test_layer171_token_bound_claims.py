"""Layer 171 — one-shot token-bound durable task claims."""

import re
from types import SimpleNamespace

from core.cognition.durable_tasks import TaskRunner, TaskStore


WORKER_ID = "20000000-0000-4000-8000-000000001711"
TOKEN_ID = "30000000-0000-4000-8000-000000001711"


class RpcClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(data=[dict(row) for row in self.rows])
        )


def test_task_store_claim_uses_exact_supplied_one_shot_token():
    request = {
        "request_id": "10000000-0000-4000-8000-000000001711",
        "message": "token-bound claim",
    }
    row = {
        "request_id": request["request_id"],
        "request": request,
        "input_hash": "0" * 64,
        "status": "running",
        "checkpoint": "starting",
        "claim_token": TOKEN_ID,
    }
    client = RpcClient([row])
    TaskStore(client).claim(WORKER_ID, claim_token=TOKEN_ID)

    assert client.calls == [
        (
            "l_task_claim_bound",
            {
                "p_worker": WORKER_ID,
                "p_claim_token": TOKEN_ID,
            },
        )
    ]


class FastStop:
    def __init__(self):
        self.flag = False

    def is_set(self):
        return self.flag

    def set(self):
        self.flag = True

    def wait(self, _timeout=None):
        return self.flag


class AmbiguousClaimStore:
    def __init__(self):
        self.tokens = []
        self.runner = None

    def claim(self, _worker, claim_token=None):
        self.tokens.append(claim_token)
        if len(self.tokens) == 1:
            raise ConnectionError("synthetic lost claim acknowledgement")
        self.runner.stop_event.set()
        return None


def test_dispatcher_retains_same_claim_token_across_transport_uncertainty():
    store = AmbiguousClaimStore()
    runner = TaskRunner(store, lambda _request: {"reply": "unused"})
    runner.stop_event = FastStop()
    store.runner = runner

    runner.loop()

    assert len(store.tokens) == 2
    assert store.tokens[0] == store.tokens[1]


class EmptyClaimStore:
    def __init__(self):
        self.tokens = []
        self.runner = None

    def claim(self, _worker, claim_token=None):
        self.tokens.append(claim_token)
        if len(self.tokens) == 2:
            self.runner.stop_event.set()
        return None


def test_successful_empty_claim_response_consumes_token_before_next_poll():
    store = EmptyClaimStore()
    runner = TaskRunner(store, lambda _request: {"reply": "unused"})
    runner.stop_event = FastStop()
    store.runner = runner

    runner.loop()

    assert len(store.tokens) == 2
    assert store.tokens[0] != store.tokens[1]


def test_layer171_migration_enforces_token_and_worker_uniqueness():
    source = open(
        "supabase/migrations/20260926065344_project_l_layer171_token_bound_claims.sql",
        encoding="utf-8",
    ).read()

    assert "add column if not exists claim_token uuid" in source
    assert "create unique index if not exists l_chat_tasks_claim_token_unique" in source
    assert "create unique index if not exists l_chat_tasks_one_running_per_worker" in source
    assert "create or replace function public.l_task_claim_bound" in source
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "worker_id=p_worker" in source
    assert "claim_token=p_claim_token" in source
    assert "lease_until >= now()" in source
    assert "when unique_violation" in source
    assert "from public, anon, authenticated" in source
    assert "to service_role;" in source


def test_layer171_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 171
