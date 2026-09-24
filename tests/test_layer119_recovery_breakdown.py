"""The browser must explain actual backend reports without hiding unassessed rows."""
import json
import subprocess

import pytest

from tests.test_layer115_recovery_readiness import task, summarise, fixture_keyring


def describe(report):
    completed = subprocess.run(
        ['node', '-e', "const {describe}=require('./ui/recovery-status.js');"
         "const fs=require('fs');console.log(JSON.stringify(describe(JSON.parse(fs.readFileSync(0,'utf8')))));"],
        input=json.dumps(report), capture_output=True, text=True,
    )
    return completed


@pytest.mark.parametrize('case', [
    'ready', 'failed_task_result', 'queued', 'running', 'interrupted', 'missing_result',
    'tampered_answer', 'bad_identifier', 'non_object', 'bad_journal', 'empty', 'partial', 'capped',
])
def test_backend_reports_reach_truthful_browser_breakdown(case):
    rows = [task(1)]
    if case in {'queued', 'running', 'interrupted'}:
        rows.append(task(2, case))
    elif case == 'failed_task_result':
        rows = [task(1, 'failed')]
    elif case == 'missing_result':
        rows[0]['result'] = None
    elif case == 'tampered_answer':
        rows[0]['result']['reply'] = 'PRIVATE tampering'
    elif case == 'bad_identifier':
        rows[0]['request_id'] = 'PRIVATE identifier'
    elif case == 'non_object':
        rows.append(None)
    elif case == 'bad_journal':
        rows[0]['request']['message'] = 'PRIVATE modified request'
    elif case == 'empty':
        rows = []
    report = summarise(rows, scan_complete=case != 'partial', capped=case == 'capped')
    result = describe(report)
    assert result.returncode == 0, result.stderr
    view = json.loads(result.stdout)
    assert 'PRIVATE' not in result.stdout
    assert f'Records checked: {len(rows)}' in view['counts']
    if case in {'bad_identifier', 'non_object'}:
        assert 'Could not assess: 1' in view['counts']
        assert 'Task records needing attention: 1' in view['ledger']
        assert 'overlap' in view['ledger']
    if case in {'missing_result', 'tampered_answer'}:
        assert 'Recovery checks failed: 1' in view['counts']
        assert 'Unfinished: 0' in view['counts']
    if case in {'queued', 'running', 'interrupted'}:
        assert 'Unfinished: 1' in view['counts']
        assert 'before sending them again' in view['guidance']
    if case in {'partial', 'capped'}:
        assert 'only the records checked' in view['guidance']
    if case == 'bad_journal':
        assert 'Results recoverable: 1' in view['counts']
        assert 'Task records needing attention: 1' in view['ledger']


@pytest.mark.parametrize('field,value', [
    ('failed_recovery_records', -1), ('unassessed_rows', 'PRIVATE'),
    ('rows_observed', 10001), ('certified_answers', 0), ('not_ready_answers', 0.5),
])
def test_invalid_or_unbalanced_counts_cannot_reach_card(field, value):
    report = summarise([task(1)])
    report['saved_answers'][field] = value
    assert describe(report).returncode != 0


@pytest.mark.parametrize('status', ['no_tasks', 'pending_tasks', 'incomplete_scan'])
def test_contradictory_status_is_rejected(status):
    report = summarise([task(1)])
    report.update(status=status, recovery_ready=False)
    assert describe(report).returncode != 0

