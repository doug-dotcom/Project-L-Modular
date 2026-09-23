"""Current-day prose can use supplied context without suppressing investigation."""
import pytest
from core.cognition.controller import plan_cognition
from core.cognition.current_update import self_contained_current_update
from core.cognition.evidence_evaluation import evidence_mode

BODY = (
    'I had breakfast and took a walk. My family called and I enjoyed the chat. '
    'I spent some time on my recovery and my project. My sleep was restful. '
    'I finished the errands and I feel pleased with my progress today.'
)

@pytest.mark.parametrize('opening', [
    'Today I got organised. ', 'This morning I got organised. ',
    'I started today feeling relaxed. ', 'My evening update: ',
    'Hey L, quick update: ', "Here’s my morning summary: ",
])
def test_clear_current_narratives_skip_history(opening):
    message = opening + BODY
    plan = plan_cognition(message)
    assert plan['signals']['self_contained_current_update']
    assert not plan['needs']['memory']
    assert not plan['needs']['longitudinal_reasoning']
    assert not evidence_mode(message, plan['needs']['memory'])

@pytest.mark.parametrize('suffix', [
    ' Compare this with my history.', ' What did we decide',
    ' Please retrieve the supporting records.', ' How has my recovery changed',
    ' We discussed our plan earlier.', ' Continue from last time.',
    ' I am still struggling.', ' Can you help me?',
])
def test_requests_and_continuity_veto_shortcut(suffix):
    assert not self_contained_current_update('Today I got organised. ' + BODY + suffix)

@pytest.mark.parametrize('message', ['Go', 'I feel proud of my recovery today.',
    'Yesterday I got organised. ' + BODY, 'My family. ' + BODY])
def test_ambiguous_turns_keep_existing_policy(message):
    assert not self_contained_current_update(message)


def test_high_stakes_still_requires_reasoning_and_external_evidence():
    plan = plan_cognition('Today I got organised. ' + BODY + ' I had a medical emergency.')
    assert plan['needs']['structured_reasoning']
    assert plan['needs']['external_evidence']


def test_explicit_history_keeps_retrieval_and_evidence():
    message = 'Today I got organised. ' + BODY + ' Deep recall my health history.'
    plan = plan_cognition(message)
    assert plan['needs']['memory']
    assert evidence_mode(message, plan['needs']['memory'])


def test_server_current_narrative_preserves_intake(monkeypatch):
    # Reuse the real server-path regression with a different synthetic input.
    from tests import test_layer93_daily_update_routing as fixture
    monkeypatch.setattr(fixture, 'UPDATE', 'Today I got organised. ' + BODY)
    fixture.test_server_skips_historical_retrieval_but_keeps_intake_and_generation(monkeypatch)
