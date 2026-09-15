from core.cognition.state_aware_response import build_state_aware_response_packet


def test_explicit_overload_reduces_cognitive_load():
    packet = build_state_aware_response_packet(
        "I'm overwhelmed, keep it simple and give me one thing at a time",
        {"conversation_phase": "active_conversation"},
    )
    assert packet["active"] is True
    assert packet["response_profile"] == "low_load"
    assert packet["confidence"] == 1.0
    assert "one next step" in packet["instruction"].lower()


def test_reflective_language_selects_reflective_profile():
    packet = build_state_aware_response_packet(
        "Help me unpack what this means for me",
        {},
    )
    assert packet["response_profile"] == "reflective"
    assert packet["governance"]["style_adaptation_only"] is True


def test_explicit_energy_can_shape_tone_without_removing_guardrails():
    packet = build_state_aware_response_packet(
        "I'm excited, let's go",
        {},
    )
    assert packet["response_profile"] == "energised"
    assert "evidence and safety boundaries" in packet["instruction"]


def test_execution_phase_is_task_focused_when_no_stronger_explicit_signal():
    packet = build_state_aware_response_packet(
        "Next step please",
        {"conversation_phase": "execution"},
    )
    assert packet["response_profile"] == "task_focused"


def test_explicit_low_load_outranks_execution_phase():
    packet = build_state_aware_response_packet(
        "Too much right now, keep it simple",
        {"conversation_phase": "execution"},
    )
    assert packet["response_profile"] == "low_load"


def test_sparse_message_does_not_invent_internal_state():
    packet = build_state_aware_response_packet("Hello", {})
    assert packet["active"] is False
    assert packet["response_profile"] == "neutral"
    assert packet["governance"]["hidden_state_claims_prohibited"] is True
    assert packet["governance"]["durable_memory_write"] is False
