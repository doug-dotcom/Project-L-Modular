"""Stage 4: curated effective-time facts, without turning mention dates into facts.

No extraction or writes from model output. The operator RPCs own all mutations.
Legacy memories remain evidence with unknown/independently interpreted validity.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import NAMESPACE_URL, UUID, uuid5
import calendar
import json
import os
import re

DEFAULT_OWNER = str(uuid5(NAMESPACE_URL, 'https://www.shinesystems.com.au/personal-memory'))
STOP = set('what is was were are the a an in on at as of current currently now today true '
           'tell me about my please recall deep has have had changed when how and for'.split())


def memory_owner():
    # A backend namespace, not a claim that a browser token is an authenticated user.
    return str(UUID(os.getenv('L_MEMORY_OWNER_ID', DEFAULT_OWNER)))


def query_terms(message):
    return list(dict.fromkeys(w for w in re.findall(r'[a-z0-9]+', message.lower())
                             if len(w) >= 2 and w not in STOP))[:24]


def query_window(message, today=None):
    today = today or datetime.now(ZoneInfo('Australia/Brisbane')).date()
    text = message.lower()
    explicit = re.search(r'\b(?:as of|on|in|at)\s+(\d{4}-\d{2}-\d{2})\b', text)
    if explicit:
        start = date.fromisoformat(explicit[1])
        return {'mode': 'historical', 'from': start.isoformat(),
                'to': (start + timedelta(days=1)).isoformat(), 'assumption': None}
    for month in range(1, 13):
        name = calendar.month_name[month].lower()
        match = re.search(r'\b(?:in|during|as of|back in)\s+' + name + r'(?:\s+(\d{4}))?\b', text)
        if match:
            year = int(match[1]) if match[1] else today.year - int(month > today.month)
            start = date(year, month, 1)
            end = date(year + int(month == 12), month % 12 + 1, 1)
            return {'mode': 'historical', 'from': start.isoformat(), 'to': end.isoformat(),
                    'assumption': None if match[1] else f'Unspecified year interpreted as {year}.'}
    # Never silently answer a historical question as if it asked about today.
    if re.search(r'\b(?:was|were|previously|formerly|used to|last year|last month|ago|history|timeline|changed)\b', text):
        return {'mode': 'timeline', 'from': None, 'to': None,
                'assumption': 'No exact historical interval supplied; show dated history, not a single current fact.'}
    return {'mode': 'current', 'from': today.isoformat(),
            'to': (today + timedelta(days=1)).isoformat(), 'assumption': None}


def select_intervals(timeline, window):
    if window['mode'] == 'timeline':
        return list(timeline)
    return [f for f in timeline if f['effective_from'] < window['to']
            and (not f.get('effective_to') or f['effective_to'] > window['from'])]


def build_temporal_packet(client, message, *, today=None, user_id=None, window_override=None):
    owner = user_id or memory_owner()
    terms = query_terms(message)
    try:
        window = window_override or query_window(message, today)
    except ValueError:
        return {'receipt': {'version': '1.0', 'status': 'needs_clarification'},
                'evidence': [], 'context': 'The requested calendar date is invalid; ask for a valid date.'}
    receipt = {'version': '1.0', 'user_id': owner, 'window': window,
               'terms': terms, 'dependencies': [], 'status': 'unavailable'}
    if client is None:
        return {'receipt': receipt, 'evidence': [], 'context': ''}
    try:
        data = client.rpc('l_fact_snapshot', {'p_user': owner, 'p_terms': terms,
                         'p_from': window['from'], 'p_to': window['to']}).execute().data
        groups = data['groups']
        selected = []
        evidence = []
        remaining = 48000
        clipped = bool(data['truncated'])
        for group in groups:
            receipt['dependencies'].append({k: group[k] for k in ('subject', 'predicate', 'revision')})
            facts = select_intervals(group['timeline'], window)
            bounded = []
            for fact in facts:
                size = len(json.dumps(fact))
                if size > remaining:
                    clipped = True
                    continue
                bounded.append(fact)
                remaining -= size
            selected.append({'subject': group['subject'], 'predicate': group['predicate'],
                             'facts': bounded, 'gap': not bool(facts), 'omitted': len(facts)-len(bounded)})
            for fact in bounded:
                evidence.append({'source': 'l_temporal_facts:' + fact['id'],
                    'quote_source': fact['source_passage'], 'role': fact['source_role'],
                    'authority': 'operator_curated', 'original_source': fact['source_ref'],
                    'effective_from': fact['effective_from'], 'effective_to': fact.get('effective_to')})
        receipt.update(status='checked', groups_checked=len(groups),
                       facts_selected=len(evidence), truncated=clipped)
        context = ('STAGE 4 — OPERATOR-CURATED FACT TIMELINES\n'
                   'Effective dates say when a claim applied. observed_at/recorded_at say when it was discussed/stored, '
                   'NOT when it became current. End dates are exclusive. Corrections replace mistaken claims; '
                   'transitions preserve earlier legitimate history. For these specific subject/property keys, '
                   'use the selected dated facts over conflicting legacy summaries or later mentions of old states. '
                   'Preserve unrelated legacy facts. A gap is unknown, not permission to resurrect an old claim. '
                   'Attribute each fact to its original source; operator curation does not mean independent proof. '
                   'Do not claim deletion or complete migration of legacy memories. '
                   'If multiple facts overlap a queried month, explain the dated changes within that month.\n'
                   + json.dumps({'window': window, 'groups': selected,
                                 'truncated': clipped}, ensure_ascii=False))
        return {'receipt': receipt, 'evidence': evidence, 'context': context}
    except Exception:
        # No raw exception/private data in response; caller must not certify stale recall.
        return {'receipt': receipt, 'evidence': [], 'context': ''}


def snapshot_freshness(client, receipt):
    if not receipt or receipt.get('status') != 'checked':
        return {'status': 'not_tracked'} if not receipt else {'status': 'unavailable'}
    try:
        return client.rpc('l_fact_freshness', {
            'p_user': receipt['user_id'], 'p_dependencies': receipt['dependencies'],
            'p_terms': receipt['terms']}).execute().data
    except Exception:
        return {'status': 'unavailable'}


def temporal_manifest():
    return {'version': '1.0', 'mode': 'operator_curated_effective_time',
            'dates': ['effective_from', 'effective_to_exclusive', 'observed_at', 'recorded_at'],
            'corrections': 'atomic_timeline_rebuild_and_dependency_freshness',
            'legacy_backfill': 'not_automatic', 'deletion': 'separate_pending_review_workflow'}
