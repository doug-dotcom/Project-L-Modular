"""Fallback image uploads recover uncertain acknowledgements without replay."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'ready', 'lost_ack', 'stalled_body', 'unresolved', 'no_double_wait',
    'rejected_type', 'rejected_size', 'rejected_id', 'late_ack', 'cleanup_failure',
    'token',
])
def test_image_answer_recovery(scenario):
    script = 'tests/image_storage_guard.test.cjs' if scenario == 'token' else 'tests/image_answer_recovery.test.cjs'
    result = subprocess.run(['node', script, scenario], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
