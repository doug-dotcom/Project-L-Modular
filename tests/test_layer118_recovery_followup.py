"""Keep recovery results dated, actionable and invalidated by new work."""
import subprocess
import pytest

@pytest.mark.parametrize('scenario', ['dated_actions', 'task_stale', 'storage_stale',
    'unrelated_storage', 'stale_pending', 'dismiss_pending'])
def test_recovery_followup(scenario):
    subprocess.run(['node', 'tests/recovery_status.test.cjs', scenario],
                   check=True, capture_output=True, text=True)
