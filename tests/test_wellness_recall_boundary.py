"""Transport and basic personal-question routing, independent of specialist workers."""
import ast
import re
from pathlib import Path
from api.wellness_chat import wellness_user_message, WELLNESS_CHAT_PREFIX

ROOT = Path(__file__).resolve().parents[1]

def controller_plan():
    # Exercise the production routing function with unrelated specialist classifiers
    # inactive; a basic family question must earn recall without a specialist cue.
    source = ast.parse((ROOT / 'core/cognition/controller.py').read_text())
    nodes = [node for node in source.body if isinstance(node, ast.FunctionDef)]
    namespace = {'re': re, 'CONTROLLER_VERSION': '2.0'}
    for name in ['self_contained_current_update', 'self_contained_daily_update',
                 'decision_recall_requested', 'personal_research_requested',
                 'timeline_query_requested', 'relationship_query_requested',
                 'needs_structured_reasoning', 'what_matters_now_requested']:
        namespace[name] = lambda message: False
    namespace['assess_present_cue'] = lambda message: {'should_retrieve': False}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'controller', 'exec'), namespace)
    return namespace['plan_cognition']

def test_wellness_question_reaches_controller_without_transport_instructions():
    question = 'Hey L how many kids do I have and what are their names'
    clean = wellness_user_message(WELLNESS_CHAT_PREFIX + question, 'wellness_example')
    assert clean == question
    assert controller_plan()(clean)['needs']['memory'] is True

def test_personal_family_variants_retrieve_without_hardcoded_answers():
    plan = controller_plan()
    for question in ['How many children do I have?', 'Who are my kids?', 'What are my children’s names?']:
        assert plan(question)['needs']['memory'] is True
    assert plan('Hello L')['needs']['memory'] is False

def test_other_threads_and_user_text_are_preserved():
    assert wellness_user_message(WELLNESS_CHAT_PREFIX + 'Hello', 'other') == WELLNESS_CHAT_PREFIX + 'Hello'
    assert wellness_user_message('My own words', 'wellness_example') == 'My own words'
