from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import pytest

from core.cognition.recall_planner import (
    plan_recall, month_windows, retrieve_period, coverage_notice, excerpt, period_terms,
)

TODAY = date(2026, 9, 6)
QUERY = 'Review recovery from 2026-03-01 to 2026-08-31'


def fixture():
    plan = plan_recall(QUERY, TODAY)
    months = [{**w, 'rows': [], 'truncated': False} for w in month_windows(plan['period'])]
    for index, month in enumerate(months):
        if index == 2:
            continue
        month['rows'] = [{'source': f'raw_catchall:{index + 1}', 'raw_id': index + 1,
                         'role': 'user', 'date': month['from'], 'date_basis': 'recorded_at',
                         'content': f"Recovery entry recorded in {month['month']}."}]
    return plan, {'months': months}


class Client:
    def __init__(self, payload, failure=False):
        self.payload, self.failure, self.calls = payload, failure, []
    def rpc(self, name, params):
        self.calls.append((name, params))
        if self.failure:
            raise RuntimeError('private database error')
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=deepcopy(self.payload)))


def run(payload=None, **kwargs):
    plan, default = fixture()
    return retrieve_period(Client(default if payload is None else payload), QUERY, plan,
                           ['recovery'], lambda text: text.endswith('?'), **kwargs)


def test_focused_is_smaller_than_deep_and_period():
    simple, deep = plan_recall('Who is Steve?', TODAY), plan_recall('Deep recall Steve', TODAY)
    assert simple['mode'] == 'focused' and deep['mode'] == 'investigate'
    assert simple['raw_candidates'] < deep['raw_candidates']
    assert not simple['gap_search'] and not simple['contradiction_review']
    assert deep['contradiction_review'] and not deep['full_scan_fallback']


def test_rolling_six_months_includes_partial_edge_months():
    plan = plan_recall('Report for Pauline over the last six months', TODAY)
    windows = month_windows(plan['period'])
    assert plan['period']['from'] == '2026-03-06'
    assert len(windows) == 7
    assert windows[-1]['through'] == '2026-09-06'


def test_month_end_and_leap_year():
    assert plan_recall('review last one month', date(2024, 3, 31))['period']['from'] == '2024-02-29'


@pytest.mark.parametrize('query', ['review last 99 months', 'review last 0 months',
    'review from 2026-02-31 to 2026-03-01', 'review from 2026-09-01 to 2026-01-01',
    'review from 2024-01-01 to 2026-01-01'])
def test_invalid_or_oversized_period_rejected(query):
    with pytest.raises(ValueError): plan_recall(query, TODAY)


def test_all_six_months_represented_and_empty_month_honest():
    packet = run()
    coverage = packet['receipt']['coverage']
    assert len(coverage) == 6
    assert coverage[2]['status'] == 'no_usable_evidence_found'
    assert packet['receipt']['months_with_evidence'] == 5
    assert '2026-05: no usable evidence found' in coverage_notice(packet['receipt'])
    assert 'does NOT mean nothing happened' in packet['context']
    assert len(packet['evidence']) == 5


def test_recent_old_mention_is_not_event_coverage():
    _, data = fixture()
    data['months'][-1]['rows'][0]['content'] = 'Recovery recollection: the event happened in March, not August.'
    packet = run(data)
    assert packet['receipt']['coverage'][-1]['event_dated_sources'] == 0
    assert packet['receipt']['coverage'][-1]['recording_dated_sources'] == 1


def test_event_date_and_source_link_preserved():
    _, data = fixture()
    row = data['months'][0]['rows'][0]
    row.update(source='episodic_memories:9', date_basis='event_date', role='assistant')
    packet = run(data)
    assert packet['receipt']['coverage'][0]['event_dated_sources'] == 1
    assert packet['evidence'][0]['raw_id'] == 1
    assert packet['evidence'][0]['role'] == 'assistant'


def test_duplicate_questions_invalid_dates_and_outside_period_excluded():
    _, data = fixture()
    base = data['months'][0]['rows'][0]
    data['months'][0]['rows'] += [deepcopy(base), {**base, 'source': 'raw_catchall:90', 'content': 'Recovery?'},
        {**base, 'source': 'raw_catchall:91', 'date': '2026-02-31'},
        {**base, 'source': 'raw_catchall:92', 'date': '2025-03-01'}]
    assert len(run(data)['receipt']['coverage'][0]['sources']) == 1


def test_candidates_cannot_crowd_out_other_months():
    _, data = fixture()
    base = data['months'][-1]['rows'][0]
    data['months'][-1]['rows'] = [{**base, 'source': f'raw_catchall:{100+i}'} for i in range(24)]
    data['months'][-1]['truncated'] = True
    packet = run(data)
    assert len(packet['receipt']['coverage'][-1]['sources']) == 6
    assert len(packet['receipt']['coverage'][0]['sources']) == 1
    assert packet['receipt']['coverage'][-1]['candidate_limit_reached']


@pytest.mark.parametrize('payload', [{}, {'months': []}, {'months': [{'month': '2026-03', 'rows': None}]}])
def test_malformed_or_missing_month_is_not_a_gap(payload):
    assert run(payload)['receipt']['status'] == 'unavailable'


def test_timeout_does_not_publish_partial_confident_context():
    times = iter([0, 13])
    packet = run(clock=lambda: next(times))
    assert packet['receipt']['status'] == 'budget_exceeded'
    assert packet['evidence'] == [] and packet['context'] == ''


def test_db_failure_no_private_error_or_retry():
    plan, data = fixture()
    client = Client(data, failure=True)
    packet = retrieve_period(client, QUERY, plan, ['recovery'], lambda _: False)
    assert packet['receipt']['status'] == 'unavailable'
    assert len(client.calls) == 1 and 'private' not in str(packet)


def test_contiguous_excerpt_and_generic_term_filter():
    content = 'x' * 1800 + ' recovery event ' + 'z' * 2000
    quote, offset, clipped = excerpt(content, ['recovery'])
    assert quote == content[offset:offset + len(quote)] and clipped
    assert 'recovery' in quote
    assert period_terms(QUERY, ['last', 'six', 'months', 'recovery', '2026']) == ['recovery']


def test_new_record_visible_without_summary_cache():
    plan, data = fixture()
    client = Client(data)
    first = retrieve_period(client, QUERY, plan, ['recovery'], lambda _: False)
    data['months'][2]['rows'] = [{**data['months'][0]['rows'][0], 'date': '2026-05-01',
                                 'source': 'raw_catchall:90'}]
    second = retrieve_period(client, QUERY, plan, ['recovery'], lambda _: False)
    assert first['receipt']['months_with_evidence'] == 5
    assert second['receipt']['months_with_evidence'] == 6
    assert len(client.calls) == 2


def test_rhee_period_path_never_calls_unbounded_legacy_context(monkeypatch):
    from agents.rhee import rhee_v3 as rhee
    _, data = fixture()
    monkeypatch.setattr(rhee, 'supabase', Client(data))
    monkeypatch.setattr(rhee, 'build_context', lambda *a, **kw: pytest.fail('legacy scan'))
    windows = []
    def temporal(*a, **kw):
        windows.append(kw['window_override'])
        return {'context': '', 'evidence': [], 'receipt': {}}
    monkeypatch.setattr(rhee, 'build_temporal_packet', temporal)
    packet = rhee.build_context_packet(QUERY)
    assert packet['recall_plan']['months_requested'] == 6
    assert packet['recall_active']
    assert windows == [{'mode': 'historical', 'from': '2026-03-01', 'to': '2026-09-01', 'assumption': None}]


def test_pauline_contract_obeys_explicit_period():
    from api.server import build_pauline_report_context
    plan = plan_recall('report for Pauline from 2026-01-01 to 2026-03-31', TODAY)
    context = build_pauline_report_context('report for Pauline', {'iso_date': '2026-09-06'}, plan)
    assert '2026-01-01 through 2026-03-31' in context


@pytest.mark.parametrize('status', ['unavailable', 'needs_clarification', 'budget_exceeded'])
def test_server_blocks_before_model_or_assistant_write(monkeypatch, status):
    from api import server
    saved = []
    monkeypatch.setattr(server, 'build_rhee_packet', lambda _: {'context': '',
        'recall_plan': {'status': status, 'message': 'Invalid period'}})
    monkeypatch.setattr(server, 'write_raw_catchall', lambda role, content, **kw: saved.append(role))
    monkeypatch.setattr(server, 'write_live_short_term', lambda *a: {'saved': True})
    monkeypatch.setattr(server, 'run_brain_pipeline', lambda _: None)
    monkeypatch.setattr(server, 'store_chat_result', lambda *a: None)
    monkeypatch.setattr(server, 'invoke_model', lambda *a, **kw: pytest.fail('model called'))
    result = server.chat(server.ChatRequest(message='Deep recall my recovery'))
    assert result['error'] and 'assistant' not in saved


def test_schema_is_backend_read_only_and_budgeted():
    sql = (Path(__file__).parents[1] / 'supabase/create_recall_period.sql').read_text().lower()
    assert 'security invoker' in sql and "statement_timeout = '8s'" in sql
    assert 'from public, anon, authenticated' in sql
    assert 'update public.' not in sql and 'delete from' not in sql
