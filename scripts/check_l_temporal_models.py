"""One-off Stage 4 provider smoke test: three synthetic requests; no database access."""
from datetime import date
from types import SimpleNamespace
from uuid import UUID
import json
import os

from openai import OpenAI
from core.cognition.temporal_memory import build_temporal_packet
from core.cognition.evidence_evaluation import evidence_prompt, evaluate_answer
from core.cognition.model_routing import configured_adapter
from core.cognition.model_independence import build_model_request, invoke_model


def run():
    old = {'id': str(UUID(int=1)), 'claim': 'prototype', 'effective_from': '2026-06-01',
           'effective_to': '2026-07-01', 'observed_at': '2026-09-05T12:00:00Z',
           'source_ref': 'synthetic:old', 'source_passage': 'Project Cedar was a prototype in June.',
           'source_role': 'document'}
    new = {**old, 'id': str(UUID(int=2)), 'claim': 'live', 'effective_from': '2026-07-01',
           'effective_to': None, 'observed_at': '2026-07-01T12:00:00Z',
           'source_ref': 'synthetic:new', 'source_passage': 'Project Cedar has been live since 1 July 2026.'}
    corrected = {**new, 'id': str(UUID(int=3)), 'claim': 'pilot', 'observed_at': '2026-09-06T12:00:00Z',
                 'source_ref': 'synthetic:correction',
                 'source_passage': 'Correction: Project Cedar has been a pilot since 1 July 2026, not live.'}
    adapter = configured_adapter(OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=45, max_retries=0),
                                 os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), os.environ)
    class Snapshot:
        def __init__(self, timeline): self.timeline = timeline
        def rpc(self, name, params):
            assert name == 'l_fact_snapshot'
            return SimpleNamespace(execute=lambda: SimpleNamespace(data={'groups': [
                {'subject': 'project cedar', 'predicate': 'status', 'revision': 2,
                 'timeline': self.timeline}], 'truncated': False}))
    results = []
    for label, query, timeline, expected in [
        ('current_after_recent_old_mention', 'What is current for Project Cedar?', [old, new], new),
        ('june_history', 'What was true for Project Cedar in June 2026?', [old, new], old),
        ('corrected_current', 'What is current for Project Cedar?', [old, corrected], corrected),
    ]:
        packet = build_temporal_packet(Snapshot(timeline), query, today=date(2026, 9, 6))
        req = build_model_request(purpose='l_user_response', routing_purpose='l_recall_response',
            messages=[{'role': 'system', 'content': packet['context'] + '\n' + evidence_prompt(packet['evidence'])},
                      {'role': 'user', 'content': query + ' Give one concise attributed fact with its exact source.'}],
            response_format={'type': 'json_object'}, max_output_tokens=2048)
        result = invoke_model(adapter, req)
        reply, audit = evaluate_answer(result['content'], packet['evidence'], model_id=result['model_id'])
        passed = (audit['status'] == 'citation_checks_passed' and audit['blocks_withheld'] == 0
                  and expected['claim'] in reply.lower()
                  and 'l_temporal_facts:' + expected['id'] in reply)
        item = {'case': label, 'passed': passed, 'citation_status': audit['status'],
                'model_receipt': result['receipt']}
        results.append(item)
        print('L_STAGE4_MODEL_CASE ' + json.dumps(item), flush=True)
        if not passed:
            raise RuntimeError('Stage 4 synthetic provider case failed')
    print('L_STAGE4_MODEL_SUMMARY ' + json.dumps({'executed': len(results),
          'passed': sum(r['passed'] for r in results), 'synthetic_only': True}), flush=True)


if __name__ == '__main__':
    run()
