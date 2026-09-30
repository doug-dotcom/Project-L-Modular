from pathlib import Path


SCRIPT = Path("scripts/verify_shine_ai_trace_trust.py")


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
