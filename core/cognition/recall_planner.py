"""Stage 5 pilot: deterministic depth planning, bounded retrieval, honest coverage.

No generated summaries are persisted. Original rows remain the source of truth.
Coverage measures supplied evidence, never completeness of a person's life.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import json
import re
import time
from zoneinfo import ZoneInfo

VERSION = '1.1'


def months_before(day, count):
    year, month = divmod(day.year * 12 + day.month - 1 - count, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def relative_day_period(text, today):
    """Resolve simple recent-time language before any broad memory search.

    These phrases describe a bounded calendar window, so they should never
    trigger a corpus-wide recall merely because the user omitted an ISO date.
    """
    if re.search(r"\byesterday(?:'s|s)?\b|\blast night\b", text):
        target = today - timedelta(days=1)
        return target, target, 'yesterday'
    if re.search(r"\btoday(?:'s|s)?\b|\bthis morning\b|\bthis afternoon\b|\btonight\b", text):
        return today, today, 'today'
    return None


def plan_recall(query, today=None):
    today = today or datetime.now(ZoneInfo('Australia/Brisbane')).date()
    text = str(query).lower()
    review = bool(re.search(r'\b(reports?|review|timeline|chronology|history|summar(?:y|ies))\b', text))
    explicit = re.search(r'\b(?:from|between)\s+(\d{4}-\d{2}-\d{2})\s+(?:to|through|and)\s+(\d{4}-\d{2}-\d{2})\b', text)
    relative = re.search(r'\b(?:last|past)\s+(\d+|one|two|three|six|twelve)\s+months?\b', text)
    six = bool(re.search(r'\bsix[- ]month|\b6[- ]month', text))
    recent_day = relative_day_period(text, today)
    period = None
    assumption = None
    period_source = None

    if recent_day:
        start, end, period_source = recent_day
        period = {
            'from': start.isoformat(),
            'through': end.isoformat(),
            'timezone': 'Australia/Brisbane',
        }
    elif review and (explicit or relative or six or 'pauline' in text or 'psychologist' in text):
        if explicit:
            start, end = (date.fromisoformat(value) for value in explicit.groups())
            period_source = 'explicit'
        else:
            number = relative.group(1) if relative else 'six'
            count = {'one': 1, 'two': 2, 'three': 3, 'six': 6, 'twelve': 12}.get(number)
            count = count if count is not None else int(number)
            if not 1 <= count <= 12:
                raise ValueError('Please request a period of one to twelve months.')
            start, end = months_before(today, count), today
            period_source = 'relative_months'
            if not relative and not six:
                assumption = 'No period specified: using the last six calendar months.'
        if start > end or (end - start).days > 366:
            raise ValueError('Please provide an ordered reporting period of at most one year.')
        period = {'from': start.isoformat(), 'through': end.isoformat(), 'timezone': 'Australia/Brisbane'}

    short_relative = period_source in ('yesterday', 'today')
    deep_signal = bool(re.search(r'\b(deep recall|compare|contradiction|conflict|changed|missing)\b', text))
    deep = deep_signal or (review and not short_relative)
    mode = 'period_review' if period else ('investigate' if deep else 'focused')

    # Budgets are target latency guardrails, not permission to discard a valid
    # bounded result that arrives slightly late. Recent-day recall gets the
    # smallest search shape; ordinary focused recall has enough headroom for
    # observed production latency without becoming an unbounded scan.
    if short_relative:
        raw_candidates = 24
        memory_candidates = 12
        selected_per_month = 8
        candidates_per_month = 16
        evidence_char_budget = 24000
        retrieval_budget_ms = 10000
    elif deep:
        raw_candidates = 200
        memory_candidates = 120
        selected_per_month = 6
        candidates_per_month = 24
        evidence_char_budget = 60000 if period else 36000
        retrieval_budget_ms = 45000
    else:
        raw_candidates = 32
        memory_candidates = 18
        selected_per_month = 6
        candidates_per_month = 20
        evidence_char_budget = 18000
        retrieval_budget_ms = 15000

    return {
        'version': VERSION,
        'mode': mode,
        'period': period,
        'period_source': period_source,
        'assumption': assumption,
        'raw_candidates': raw_candidates,
        'memory_candidates': memory_candidates,
        'selected_per_month': selected_per_month,
        'candidates_per_month': candidates_per_month,
        'evidence_char_budget': evidence_char_budget,
        'retrieval_budget_ms': retrieval_budget_ms,
        'gap_search': bool(period) and not short_relative,
        'contradiction_review': deep,
        'full_scan_fallback': False,
    }


def month_windows(period):
    start, end = date.fromisoformat(period['from']), date.fromisoformat(period['through'])
    cursor = start.replace(day=1)
    windows = []
    while cursor <= end:
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        windows.append({'month': cursor.strftime('%Y-%m'), 'from': max(start, cursor).isoformat(),
                        'through': min(end, next_month - timedelta(days=1)).isoformat()})
        cursor = next_month
    return windows


def period_terms(query, terms):
    # Do not let generic report/date words swamp topical evidence.
    stop = {'report', 'reports', 'review', 'summary', 'summaries', 'history', 'timeline', 'chronology',
            'last', 'past', 'today', 'todays', "today's", 'yesterday', 'yesterdays', "yesterday's",
            'night', 'morning', 'afternoon', 'six', 'months', 'month', 'based', 'full', 'write',
            'through', 'between', 'from', 'give', 'make', 'create', 'personal', 'life'}
    return list(dict.fromkeys(t for t in terms if t not in stop and not t.isdigit()))[:24]


def excerpt(content, terms, limit=1200):
    """One continuous source slice; never join separated fragments into a quote."""
    content = str(content or '')
    hits = [match.start() for term in terms if (match := re.search(r'\b' + re.escape(term), content, re.I))]
    start = max(0, min(hits) - 160) if hits else 0
    return content[start:start + limit], start, len(content) > limit


def retrieve_period(client, query, plan, terms, is_artifact, clock=time.monotonic):
    started = clock()
    receipt = {**plan, 'status': 'checked', 'coverage': [], 'source_count': 0,
               'search_calls': 0, 'raw_evidence_preserved': True,
               'coverage_meaning': 'supplied evidence only; not real-world completeness',
               'semantic_relevance': 'not_independently_verified', 'incremental_summary_cache': False}
    if not client:
        receipt['status'] = 'unavailable'
        return {'context': '', 'evidence': [], 'receipt': receipt}
    terms = period_terms(query, terms)
    try:
        receipt['search_calls'] = 1
        result = client.rpc('l_recall_period', {'p_from': plan['period']['from'],
            'p_through': plan['period']['through'], 'p_terms': terms,
            'p_per_month': plan['candidates_per_month']}).execute().data
        if not isinstance(result, dict) or not isinstance(result.get('months'), list):
            raise ValueError('Invalid period result')
    except Exception:
        receipt.update(status='unavailable', latency_ms=round((clock() - started) * 1000))
        return {'context': '', 'evidence': [], 'receipt': receipt}

    elapsed = round((clock() - started) * 1000)
    receipt['latency_ms'] = elapsed
    receipt['budget_exceeded'] = elapsed > plan['retrieval_budget_ms']
    receipt['timing_status'] = (
        'late_bounded_result' if receipt['budget_exceeded'] else 'within_budget'
    )
    # A completed bounded database query is still valid evidence. The old path
    # discarded the entire result solely because it arrived after the target
    # latency, causing a false "could not complete" error even when candidates
    # were already present. Preserve the bounded result and surface its timing
    # in the receipt instead.

    by_month = {m.get('month'): m for m in result['months'] if isinstance(m, dict)}
    evidence, groups, used = [], [], 0
    for window in month_windows(plan['period']):
        supplied = by_month.get(window['month'])
        if supplied is None or not isinstance(supplied.get('rows'), list):
            receipt['status'] = 'unavailable'
            return {'context': '', 'evidence': [], 'receipt': receipt}
        selected, seen = [], set()
        for row in supplied['rows']:
            if not isinstance(row, dict):
                continue
            content = str(row.get('content') or '')
            source = str(row.get('source') or '')
            if not re.fullmatch(r'(raw_catchall|episodic_memories):\d+', source):
                continue
            if source in seen or not content or is_artifact(content):
                continue
            # Event date is explicit metadata. Recording date never proves event timing.
            basis = row.get('date_basis')
            try:
                day = date.fromisoformat(str(row.get('date')))
            except ValueError:
                continue
            if not window['from'] <= day.isoformat() <= window['through']:
                continue
            if basis not in ('event_date', 'recorded_at'):
                continue
            quote, offset, clipped = excerpt(content, terms)
            cost = len(quote)
            if used + cost > plan['evidence_char_budget']:
                break
            seen.add(source)
            used += cost
            item = {'source': source, 'quote_source': quote, 'role': row.get('role', 'unknown'),
                    'date': day.isoformat(), 'date_basis': basis,
                    'raw_id': row.get('raw_id'), 'excerpt_offset': offset,
                    'truncated': clipped or row.get('truncated', False)}
            evidence.append(item)
            selected.append(item)
            if len(selected) >= plan['selected_per_month']:
                break
        event_count = sum(row['date_basis'] == 'event_date' for row in selected)
        coverage = {**window, 'sources': [row['source'] for row in selected],
                    'event_dated_sources': event_count, 'recording_dated_sources': len(selected) - event_count,
                    'status': 'evidence_found' if selected else 'no_usable_evidence_found',
                    'candidate_limit_reached': bool(supplied.get('truncated')),
                    'selection_limited': len(supplied['rows']) > len(selected)}
        receipt['coverage'].append(coverage)
        groups.append({'window': window, 'coverage': coverage, 'source_linked_extracts': selected})
    receipt.update(source_count=len(evidence), evidence_chars=used,
                   months_with_evidence=sum(bool(m['sources']) for m in receipt['coverage']),
                   months_requested=len(receipt['coverage']))
    context = ('STAGE 5 PERIOD REVIEW — bounded evidence pilot\n'
        'Use the exact requested period below. Cover every listed month; explicitly identify gaps. '
        'No usable evidence found does NOT mean nothing happened. Selection and candidate limits are not complete recall. '
        'A recording timestamp dates the record, NOT the event it describes. Do not place an old event in the month it was retold. '
        'Only event_date metadata or an explicit date in the supplied passage can support event chronology. '
        'Summarise the source-linked extracts, retain citations and source roles, and preserve uncertainty. '
        'Do not infer continuity between isolated episodes. Conflicting passages must be disclosed, not silently reconciled. '
        'Current Stage 4 curated facts take precedence only for their registered subject/property. '
        'Original full raw records remain stored; truncated passages do not license filling missing text.\n'
        + json.dumps({'period': plan['period'], 'assumption': plan['assumption'], 'months': groups}, ensure_ascii=False))
    return {'context': context, 'evidence': evidence, 'receipt': receipt}


def coverage_notice(receipt):
    if not receipt or receipt.get('mode') != 'period_review' or receipt.get('status') != 'checked':
        return ''
    lines = ['Retrieval coverage (bounded search; not proof of complete history):']
    for month in receipt.get('coverage', []):
        count = len(month['sources'])
        label = (f"{count} supplied sources ({month['event_dated_sources']} event-dated; "
                 f"{month['recording_dated_sources']} recording-dated)") if count else 'no usable evidence found'
        if month['candidate_limit_reached'] or month['selection_limited']:
            label += '; selection limited'
        lines.append(f"- {month['month']}: {label}.")
    return '\n'.join(lines)


def planner_manifest():
    return {'version': VERSION, 'stage': 5, 'status': 'bounded_pilot',
            'modes': ['focused', 'investigate', 'period_review'],
            'relative_day_fast_path': True,
            'late_bounded_evidence_preserved': True,
            'max_period_days': 366, 'persistent_summaries': False,
            'complete_recall_certified': False}
