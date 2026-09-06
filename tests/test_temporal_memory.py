from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.cognition.temporal_memory import (
    build_temporal_packet, query_window, query_terms, select_intervals, snapshot_freshness,
)
from core.cognition.evidence_evaluation import evaluate_answer


TODAY = date(2026, 9, 6)
OLD = {'id': str(uuid4()), 'claim': 'prototype', 'effective_from': '2026-06-01',
       'effective_to': '2026-07-01', 'observed_at': '2026-09-05T00:00:00+00:00',
       'source_ref': 'fixture:old', 'source_passage': 'Project Cedar was a prototype in June.',
       'source_role': 'document'}
NEW = {**OLD, 'id': str(uuid4()), 'claim': 'live', 'effective_from': '2026-07-01',
       'effective_to': None, 'observed_at': '2026-07-01T00:00:00+00:00',
       'source_ref': 'fixture:new', 'source_passage': 'Project Cedar is live from July.'}


class Client:
    def __init__(self, groups=None, failure=False):
        self.groups = groups if groups is not None else [{'subject': 'project cedar', 'predicate': 'status',
                                                         'revision': 2, 'timeline': [OLD, NEW]}]
        self.calls = []
        self.failure = failure
    def rpc(self, name, params):
        self.calls.append((name, params))
        if self.failure:
            raise RuntimeError('private database detail')
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=
            {'groups': deepcopy(self.groups), 'truncated': False} if name == 'l_fact_snapshot'
            else {'status': 'unchanged'}))


def test_current_ignores_recent_mention_of_old_state():
    packet = build_temporal_packet(Client(), 'What is current for Project Cedar?', today=TODAY)
    assert [row['original_source'] for row in packet['evidence']] == ['fixture:new']
    assert 'prototype' not in packet['context']
    assert packet['receipt']['dependencies'][0]['revision'] == 2


def test_june_uses_effective_dates_not_observation_dates():
    packet = build_temporal_packet(Client(), 'What was true for Project Cedar in June?', today=TODAY)
    assert [row['original_source'] for row in packet['evidence']] == ['fixture:old']
    assert packet['receipt']['window']['assumption'] == 'Unspecified year interpreted as 2026.'


def test_interval_boundaries_and_gaps():
    assert select_intervals([OLD, NEW], query_window('as of 2026-07-01', TODAY)) == [NEW]
    assert select_intervals([OLD, NEW], query_window('as of 2026-05-31', TODAY)) == []
    assert select_intervals([OLD, NEW], query_window('in June 2026', TODAY)) == [OLD]


def test_multiple_changes_in_month_are_all_returned():
    middle = {**NEW, 'effective_from': '2026-06-15'}
    first = {**OLD, 'effective_to': '2026-06-15'}
    assert select_intervals([first, middle], query_window('in June 2026', TODAY)) == [first, middle]


@pytest.mark.parametrize('question', ['What was Project Cedar?', 'Cedar last year', 'Cedar history', 'How has Cedar changed?'])
def test_ambiguous_history_does_not_silently_become_current(question):
    assert query_window(question, TODAY)['mode'] == 'timeline'


def test_year_rollover_is_explicit():
    assert query_window('in December', TODAY)['from'] == '2025-12-01'
    assert query_window('in December 2024', TODAY)['from'] == '2024-12-01'


def test_bad_date_is_not_silently_current():
    with pytest.raises(ValueError):
        query_window('as of 2026-02-31', TODAY)


def test_fact_evidence_preserves_authorship_and_original_source():
    packet = build_temporal_packet(Client(), 'Project Cedar status', today=TODAY)
    row = packet['evidence'][0]
    assert row['role'] == 'document'
    assert row['authority'] == 'operator_curated'
    draft = json.dumps({'blocks': [{'kind': 'fact', 'text': 'The recorded status is live.',
                       'citations': [{'source': row['source'], 'quote': 'is live from July'}]}]})
    _, audit = evaluate_answer(draft, packet['evidence'])
    assert audit['status'] == 'citation_checks_passed'
    assert audit['semantic_accuracy'] == 'not_independently_verified'


def test_assistant_legacy_rows_cannot_self_promote_by_authority_label():
    rows = [{'source': 'raw_catchall:42', 'quote_source': 'a personal fact',
             'role': 'assistant', 'authority': 'operator_curated'}]
    draft = json.dumps({'blocks': [{'kind': 'fact', 'text': 'A personal fact',
                       'citations': [{'source': 'raw_catchall:42', 'quote': 'a personal fact'}]}]})
    _, audit = evaluate_answer(draft, rows)
    assert audit['status'] == 'blocked'


def test_unavailable_database_fails_closed_without_private_error():
    packet = build_temporal_packet(Client(failure=True), 'Cedar', today=TODAY)
    assert packet['receipt']['status'] == 'unavailable'
    assert 'private database' not in str(packet)
    assert snapshot_freshness(Client(), packet['receipt'])['status'] == 'unavailable'


def test_empty_snapshot_tracks_query_for_newly_added_facts():
    client = Client(groups=[])
    packet = build_temporal_packet(client, 'Project Cedar status', today=TODAY)
    assert packet['receipt']['status'] == 'checked'
    snapshot_freshness(client, packet['receipt'])
    assert client.calls[-1][1]['p_terms'] == ['project', 'cedar', 'status']
    assert client.calls[-1][1]['p_dependencies'] == []


def test_queries_are_bounded_and_not_sql_fragments():
    assert len(query_terms(' '.join(f'word{x}' for x in range(50)))) == 24
    assert all("'" not in t for t in query_terms("Cedar'); drop table facts; --"))


def test_durable_result_is_immutable_when_facts_change():
    from core.cognition.durable_tasks import TaskStore
    payload = {'reply': 'Original answer', 'cognition': {'temporal_memory': {
        'status': 'checked', 'user_id': str(uuid4()), 'dependencies': [], 'terms': ['cedar']}}}
    stored = deepcopy(payload)
    class Query:
        def select(self, *a): return self
        def eq(self, *a): return self
        def limit(self, *a): return self
        def execute(self): return SimpleNamespace(data=[{'status': 'ready', 'result': stored}])
    class DB:
        def table(self, name): return Query()
        def rpc(self, name, params):
            return SimpleNamespace(execute=lambda: SimpleNamespace(data={'status': 'superseded'}))
    result = TaskStore(DB()).get(str(uuid4()), 'a' * 64)
    assert result['freshness']['status'] == 'superseded'
    assert result['result'] == payload == stored


def test_rhee_wires_curated_facts_into_live_context(monkeypatch):
    from agents.rhee import rhee_v3 as rhee
    monkeypatch.setattr(rhee, 'supabase', Client())
    monkeypatch.setattr(rhee, 'build_context', lambda *a, **k: 'legacy context')
    packet = rhee.build_context_packet('Project Cedar status')
    assert 'STAGE 4' in packet['context']
    assert packet['temporal_memory']['status'] == 'checked'
    assert packet['evidence']


def test_ui_warns_without_overwriting_saved_receipts():
    ui = (Path(__file__).parents[1] / 'ui/index.html').read_text()
    assert 'savedAnswerText(data)' in ui and 'savedAnswerText(result)' in ui
    assert 'relevant facts have since changed' in ui


def test_schema_restricts_all_new_mutations_and_has_no_legacy_updates():
    sql = (Path(__file__).parents[1] / 'supabase/create_temporal_facts.sql').read_text()
    assert sql.count('enable row level security') == 4
    assert 'security definer' not in sql.lower()
    assert 'update public.raw_catchall' not in sql.lower()
    assert 'delete from' not in sql.lower()
    assert 'for update' in sql.lower()


@pytest.mark.parametrize('status', ['unavailable', 'needs_clarification'])
def test_chat_does_not_generate_or_save_assistant_when_timeline_unavailable(monkeypatch, status):
    from api import server
    saved = []
    monkeypatch.setattr(server, 'build_rhee_packet', lambda _: {
        'context': '', 'temporal_memory': {'status': status}})
    monkeypatch.setattr(server, 'write_raw_catchall', lambda role, content, **kw: saved.append(role))
    monkeypatch.setattr(server, 'write_live_short_term', lambda *a: {'saved': True})
    monkeypatch.setattr(server, 'run_brain_pipeline', lambda _: None)
    result = server.chat(server.ChatRequest(message='Deep recall Project Cedar status'))
    assert result['error']
    assert 'assistant' not in saved


def test_correction_during_generation_withholds_answer_before_memory_write(monkeypatch):
    from api import server
    saved = []
    class Adapter:
        available = True
        provider = 'test'
        model_id = 'test'
        def generate(self, request):
            return {'content': json.dumps({'blocks': [{'kind': 'unknown', 'text': 'No fact known.'}]})}
    monkeypatch.setattr(server, 'resolve_model_adapter', lambda: Adapter())
    monkeypatch.setattr(server, 'build_rhee_packet', lambda _: {'context': '', 'evidence': [],
        'temporal_memory': {'status': 'checked', 'dependencies': [], 'terms': ['cedar']}})
    monkeypatch.setattr(server, 'snapshot_freshness', lambda *a: {'status': 'superseded'})
    monkeypatch.setattr(server, 'route_capability', lambda _: {'handled': False, 'status': 'not_required'})
    monkeypatch.setattr(server, 'run_cognitive_core', lambda *a, **kw: {})
    monkeypatch.setattr(server, 'write_raw_catchall', lambda role, content, **kw: saved.append(role))
    monkeypatch.setattr(server, 'write_live_short_term', lambda *a: {'saved': True})
    monkeypatch.setattr(server, 'run_brain_pipeline', lambda _: None)
    result = server.chat(server.ChatRequest(message='Deep recall Project Cedar status'))
    assert result['error']
    assert 'timeline changed' in result['reply']
    assert 'assistant' not in saved
