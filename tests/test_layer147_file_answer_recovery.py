"""Account file questions retain recovery handles and use bounded waits."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'ready', 'lost_ack', 'stalled_ack', 'stalled_poll', 'stalled_body',
    'pending', 'pending_again', 'history_cleanup', 'cleanup_failure',
    'newer_pending', 'voice_failure', 'transient_poll',
])
def test_file_answer_recovery(scenario):
    result = subprocess.run(['node', 'tests/file_answer_recovery.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
