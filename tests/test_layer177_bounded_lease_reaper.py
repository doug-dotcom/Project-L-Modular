"""Layer 177 — lease expiry is bounded and separate from claiming."""

import re
from types import SimpleNamespace

from core.cognition.durable_tasks import TaskStore


class RpcClient:
    def __init__(self):
        self.calls = []
    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=0))


def test_task_store_exposes_bounded_reaper_rpc():
    client = RpcClient()
    store = TaskStore(client)
    assert store.reap_expired(limit=37) == 0
    assert client.calls == [("l_task_reap_expired", {"p_limit": 37})]


def test_layer177_claim_function_no_longer_globally_reaps():
    source = open(
        "supabase/migrations/20260926084955_project_l_layer177_bounded_lease_reaper.sql",
        encoding="utf-8",
    ).read().lower()
    claim = source[source.index("create or replace function public.l_task_claim_bound"):]
    assert "set status='interrupted'" not in claim
    assert "l_task_reap_expired" in source
    assert "for update skip locked" in source
    assert "least(coalesce(p_limit, 100), 500)" in source


def test_dispatcher_reaps_before_claiming():
    source = open("core/cognition/durable_tasks.py", encoding="utf-8").read()
    loop = source[source.index("    def loop(self):"):source.index("    def _persist_terminal_bound")]
    assert loop.index("self.store.reap_expired(limit=100)") < loop.index("self.store.claim(")


def test_layer177_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers=[int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)',source)]
    assert len(layers)==3 and len(set(layers))==1 and layers[0]>=177
