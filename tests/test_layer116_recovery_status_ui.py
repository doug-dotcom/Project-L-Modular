"""Exercise user-triggered recovery status, privacy, retries and account changes."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', [
    'ready', 'ready_with_legacy', 'pending_tasks', 'needs_attention',
    'incomplete_scan', 'no_tasks', 'invalid', 'on_demand', 'retry',
    'duplicate', 'account_change', 'account_locked',
])
def test_recovery_status_browser_behaviour(scenario):
    subprocess.run(['node', 'tests/recovery_status.test.cjs', scenario], check=True, capture_output=True, text=True)
