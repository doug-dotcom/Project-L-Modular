"""Layer 175 — durable submission self-verifies request identity and hash."""
import re
from pathlib import Path

P=Path("supabase/migrations/20260926081725_project_l_layer175_self_verifying_submission.sql")

def test_submit_recomputes_hash_inside_postgres():
    s=P.read_text(encoding="utf-8")
    assert "extensions.digest" in s
    assert "convert_to(p_request::text,'UTF8')" in s
    assert "expected_hash <> p_hash" in s

def test_submit_binds_embedded_request_id_before_insert():
    s=P.read_text(encoding="utf-8")
    assert s.index("p_request->>'request_id' is distinct from p_id::text") < s.index("insert into public.l_chat_tasks")

def test_submit_validates_owner_and_hash_shapes():
    s=P.read_text(encoding="utf-8")
    assert "length(p_owner) <> 64" in s
    assert "p_owner !~ '^[0-9a-f]{64}$'" in s
    assert "p_hash !~ '^[0-9a-f]{64}$'" in s

def test_existing_request_must_match_exact_request():
    assert "t.input_hash<>p_hash or t.request<>p_request" in P.read_text(encoding="utf-8")

def test_submit_remains_backend_only():
    s=P.read_text(encoding="utf-8")
    assert "security invoker" in s and "from public,anon,authenticated;" in s and "to service_role;" in s

def test_layer175_release_marker_is_continuous():
    s=Path("api/server.py").read_text(encoding="utf-8")
    layers=[int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)',s)]
    assert len(layers)==3 and len(set(layers))==1 and layers[0]>=175
