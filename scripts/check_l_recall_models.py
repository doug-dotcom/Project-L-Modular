"""One-off Stage 5 synthetic provider check. No database access or private memory."""
from datetime import date
from types import SimpleNamespace
import json
import os

from openai import OpenAI
from core.cognition.recall_planner import plan_recall, month_windows, retrieve_period
from core.cognition.evidence_evaluation import evidence_prompt, evaluate_answer
from core.cognition.model_routing import configured_adapter
from core.cognition.model_independence import build_model_request, invoke_model


def run():
    query = 'Review Project Cedar from 2026-03-01 to 2026-08-31'
    plan = plan_recall(query, date(2026, 9, 6))
    adapter = configured_adapter(OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=45, max_retries=0),
                                 os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), os.environ)
    results = []
    for case in ['sparse_six_month_review', 'recent_old_mention']:
        months = [{**w, 'rows': [], 'truncated': False} for w in month_windows(plan['period'])]
        for i in [0, 1, 3, 4]:
            month = months[i]
            month['rows'] = [{'source': f'episodic_memories:{900+i}', 'raw_id': 800+i,
                'role': 'user', 'date': month['from'], 'date_basis': 'event_date',
                'content': f"Project Cedar completed checkpoint {i+1} on {month['from']}."}]
        if case == 'recent_old_mention':
            months[-1]['rows'] = [{'source': 'raw_catchall:999', 'raw_id': 999, 'role': 'user',
                'date': '2026-08-15', 'date_basis': 'recorded_at',
                'content': 'Project Cedar recollection recorded on 2026-08-15: checkpoint 1 happened on 2026-03-01. No August milestone is documented here.'}]
        class Snapshot:
            def rpc(self, name, params):
                assert name == 'l_recall_period'
                return SimpleNamespace(execute=lambda: SimpleNamespace(data={'months': months}))
        packet = retrieve_period(Snapshot(), query, plan, ['cedar'], lambda _: False)
        request = build_model_request(purpose='l_user_response', routing_purpose='l_recall_response',
            messages=[{'role': 'system', 'content': packet['context'] + '\n' + evidence_prompt(packet['evidence'])},
                      {'role': 'user', 'content': query + '. Use exactly six short blocks, one per month, '
                       'starting each with its YYYY-MM label. Admit missing evidence for May and missing '
                       'event evidence for August; do not move a March checkpoint to August.'}],
            response_format={'type': 'json_object'}, max_output_tokens=3000)
        result = invoke_model(adapter, request)
        reply, audit = evaluate_answer(result['content'], packet['evidence'], model_id=result['model_id'])
        blocks = json.loads(result['content']).get('blocks', [])
        indexed = {str(b.get('text', ''))[:7]: b for b in blocks}
        gaps = all(indexed.get(m, {}).get('kind') == 'unknown' for m in ['2026-05', '2026-08'])
        passed = (audit['status'] == 'citation_checks_passed' and audit['blocks_withheld'] == 0
                  and all(w['month'] in indexed for w in months) and gaps
                  and all(f'episodic_memories:{900+i}' in reply for i in [0, 1, 3, 4]))
        item = {'case': case, 'passed': passed, 'months_represented': len(indexed),
                'gap_blocks_correct': gaps, 'citation_status': audit['status'],
                'retrieval_receipt': {k: packet['receipt'][k] for k in
                    ('latency_ms', 'months_requested', 'months_with_evidence', 'source_count')},
                'model_receipt': result['receipt']}
        results.append(item)
        print('L_STAGE5_MODEL_CASE ' + json.dumps(item), flush=True)
        if not passed:
            raise RuntimeError('Stage 5 synthetic provider case failed')
    print('L_STAGE5_MODEL_SUMMARY ' + json.dumps({'executed': len(results),
          'passed': sum(r['passed'] for r in results), 'synthetic_only': True}), flush=True)


if __name__ == '__main__':
    run()
