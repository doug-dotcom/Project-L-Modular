"""Layer 181 — connected-action journal is write-once in Postgres."""

import re
from pathlib import Path


def test_layer181_recorded_action_receipt_is_immutable():
    source=Path(
        "supabase/migrations/20260926122243_project_l_layer181_immutable_action_journal.sql"
    ).read_text(encoding="utf-8").lower()
    assert "old.action_receipt is not null" in source
    assert "new.action_receipt is distinct from old.action_receipt" in source
    assert "errcode = '23514'" in source


def test_layer181_first_write_requires_confirmed_request_bound_receipt():
    source=Path(
        "supabase/migrations/20260926122243_project_l_layer181_immutable_action_journal.sql"
    ).read_text(encoding="utf-8").lower()
    assert "old.status <> 'running'" in source
    assert "new.status <> 'running'" in source
    assert "request_id' is distinct from old.request_id::text" in source
    assert "status' <> 'confirmed'" in source
    assert "resource_id','') = ''" in source
    assert "new.checkpoint <> 'connected_action_recorded'" in source


def test_layer181_trigger_function_is_not_directly_executable():
    source=Path(
        "supabase/migrations/20260926122243_project_l_layer181_immutable_action_journal.sql"
    ).read_text(encoding="utf-8").lower()
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "from public, anon, authenticated, service_role;" in source


def test_layer181_release_marker_is_continuous():
    source=Path("api/server.py").read_text(encoding="utf-8")
    layers=[int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)',source)]
    assert len(layers)==3 and len(set(layers))==1 and layers[0]>=181
