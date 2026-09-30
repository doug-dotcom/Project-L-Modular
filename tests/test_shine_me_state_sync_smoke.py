"""Contract tests for the production-safe Shine Me owner-state smoke."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_shine_me_state_sync.py"


def load_smoke():
    spec = importlib.util.spec_from_file_location("shine_me_state_sync_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, columns):
        assert columns == "owner_id,state,revision,updated_at"
        return self

    def eq(self, field, value):
        assert field == "owner_id"
        self.owner = value
        return self

    def limit(self, count):
        assert count == 1
        return self

    def execute(self):
        return Result(self.rows)


class Client:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "shine_me_owner_state"
        return Query(self.rows)


def test_smoke_prints_receipt_not_personal_state(monkeypatch, capsys):
    smoke = load_smoke()
    owner = "owner-private"
    secret = "private journal words that must never appear in deploy logs"
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-secret")
    monkeypatch.setenv("PROJECT_L_OWNER_ID", owner)
    monkeypatch.setenv("L_MEMORY_OWNER_ID", owner)
    monkeypatch.setattr(
        smoke,
        "create_client",
        lambda *_: Client([{
            "owner_id": owner,
            "state": {"journal": [{"reflection": secret}]},
            "revision": 4,
            "updated_at": "2026-10-01T00:00:00+00:00",
        }]),
    )

    smoke.main()
    output = capsys.readouterr().out
    assert "Project L Shine-Me state sync smoke: PASS" in output
    assert "binding=server-verified" in output
    assert "state=present" in output
    assert "revision=4" in output
    assert owner not in output
    assert secret not in output
    assert "service-secret" not in output


def test_smoke_accepts_empty_owner_state(monkeypatch, capsys):
    smoke = load_smoke()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-secret")
    monkeypatch.setenv("PROJECT_L_OWNER_ID", "owner-a")
    monkeypatch.setenv("L_MEMORY_OWNER_ID", "owner-a")
    monkeypatch.setattr(smoke, "create_client", lambda *_: Client([]))

    smoke.main()
    output = capsys.readouterr().out
    assert "state=empty" in output
    assert "revision=0" in output


def test_smoke_fails_closed_on_owner_binding_mismatch(monkeypatch):
    smoke = load_smoke()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-secret")
    monkeypatch.setenv("PROJECT_L_OWNER_ID", "owner-a")
    monkeypatch.setenv("L_MEMORY_OWNER_ID", "owner-b")

    try:
        smoke.main()
    except SystemExit as exc:
        assert "owner-binding-mismatch" in str(exc)
    else:
        raise AssertionError("smoke should fail closed")
