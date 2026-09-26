"""Layer 176 — durable recovery is owner-bound inside Postgres."""

import re
from types import SimpleNamespace

from core.cognition.durable_tasks import TaskStore, owner_identity


REQUEST_ID = "10000000-0000-4000-8000-000000001761"
TOKEN = "x" * 64


class RpcClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.rows))


def test_task_store_recovery_uses_owner_bound_rpc():
    client = RpcClient([])
    store = TaskStore(client)

    assert store.get(REQUEST_ID, TOKEN) == {"status": "not_found"}

    user_id, owner = owner_identity(TOKEN)
    assert client.calls == [
        (
            "l_task_recover_bound",
            {
                "p_id": REQUEST_ID,
                "p_user": user_id,
                "p_owner": owner,
            },
        )
    ]


def test_runtime_no_longer_reads_durable_task_table_directly_for_recovery():
    source = open("core/cognition/durable_tasks.py", encoding="utf-8").read()
    get_start = source.index("    def get(self, request_id, token):")
    claim_start = source.index("    def claim(", get_start)
    get_source = source[get_start:claim_start]

    assert "l_task_recover_bound" in get_source
    assert ".table('l_chat_tasks')" not in get_source
    assert ".eq('owner_hash'" not in get_source


def test_layer176_recovery_rpc_is_read_only_owner_bound_and_backend_only():
    source = open(
        "supabase/migrations/20260926084112_project_l_layer176_owner_bound_recovery.sql",
        encoding="utf-8",
    ).read().lower()

    assert "create or replace function public.l_task_recover_bound" in source
    assert "language sql" in source
    assert "security invoker" in source
    assert "stable" in source
    assert "t.request_id = p_id" in source
    assert "t.user_id = p_user" in source
    assert "t.owner_hash = p_owner" in source
    assert "length(p_owner) = 64" in source
    assert "update public.l_chat_tasks" not in source
    assert "insert into public.l_chat_tasks" not in source
    assert "from public, anon, authenticated" in source
    assert "to service_role;" in source


def test_layer176_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(v)
        for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 176
