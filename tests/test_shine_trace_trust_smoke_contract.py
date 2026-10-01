import importlib.util
from pathlib import Path


SCRIPT = Path("scripts/verify_shine_ai_trace_trust.py")


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_shine_ai_trace_trust",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_generation_one_zero_row_evidence_chain_is_not_coerced_to_missing():
    text = source()

    assert (
        'quorum.get(\n'
        '            "external_roster_transition_evidence_chain_rows"\n'
        '        ) != 0'
    ) in text
    assert (
        'external_roster_transition_evidence_chain_rows")\n'
        '            or -1'
    ) not in text



def test_trace_trust_smoke_uses_bounded_http1_database_transport():
    text = source()

    assert "SMOKE_DB_TIMEOUT_SECONDS = 5.0" in text
    assert "http2=False" in text
    assert "connect=3.0" in text
    assert "max_connections=2" in text
    assert "SyncClientOptions" in text
    assert "auto_refresh_token=False" in text
    assert "persist_session=False" in text



def test_trace_trust_snapshot_recovery_is_bounded(monkeypatch):
    smoke = load_module()
    calls = []
    sleeps = []
    outcomes = [
        (None, smoke.TRACE_SNAPSHOT_TRANSIENT_REASON),
        (None, smoke.TRACE_SNAPSHOT_TRANSIENT_REASON),
        ({"storage": {}}, None),
    ]

    def seal(db):
        calls.append(db)
        return outcomes[len(calls) - 1]

    monkeypatch.setattr(
        smoke.runtime,
        "_seal_existing_trace_trust_state",
        seal,
    )
    monkeypatch.setattr(smoke.time, "sleep", sleeps.append)
    monkeypatch.setattr(smoke, "_reset_cache", lambda: None)

    sealed, error, replays = smoke._seal_with_snapshot_recovery("db")

    assert sealed == {"storage": {}}
    assert error is None
    assert replays == 2
    assert len(calls) == 3
    assert sleeps == [2.0, 5.0]


def test_trace_trust_snapshot_recovery_does_not_retry_security_failure(monkeypatch):
    smoke = load_module()
    calls = []
    sleeps = []

    def seal(db):
        calls.append(db)
        return None, "foundation-chain-unverified"

    monkeypatch.setattr(
        smoke.runtime,
        "_seal_existing_trace_trust_state",
        seal,
    )
    monkeypatch.setattr(smoke.time, "sleep", sleeps.append)
    monkeypatch.setattr(smoke, "_reset_cache", lambda: None)

    sealed, error, replays = smoke._seal_with_snapshot_recovery("db")

    assert sealed is None
    assert error == "foundation-chain-unverified"
    assert replays == 0
    assert len(calls) == 1
    assert sleeps == []


def test_trace_trust_keyset_snapshot_recovery_is_bounded(monkeypatch):
    smoke = load_module()
    calls = []
    sleeps = []
    outcomes = [
        (None, smoke.TRACE_SNAPSHOT_TRANSIENT_REASON, {"status": "unavailable"}),
        (
            {"generation": 1, "verification_keys": {"k1": "x"}},
            None,
            {"status": "trusted"},
        ),
    ]

    def keyset(db):
        calls.append(db)
        return outcomes[len(calls) - 1]

    monkeypatch.setattr(
        smoke.runtime,
        "_shine_ai_verification_keyset",
        keyset,
    )
    monkeypatch.setattr(smoke.time, "sleep", sleeps.append)
    monkeypatch.setattr(smoke, "_reset_cache", lambda: None)

    keyset, error, trust, replays = smoke._keyset_with_snapshot_recovery("db")

    assert keyset["generation"] == 1
    assert error is None
    assert trust["status"] == "trusted"
    assert replays == 1
    assert len(calls) == 2
    assert sleeps == [2.0]


def test_trace_trust_smoke_contract_names_only_transient_snapshot_reason():
    text = source()

    assert (
        'TRACE_SNAPSHOT_TRANSIENT_REASON = '
        '"trace-trust-snapshot-unavailable"'
    ) in text
    assert "TRACE_SNAPSHOT_RETRY_DELAYS_SECONDS = (2.0, 5.0)" in text
    assert "snapshot_replays=" in text
