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
