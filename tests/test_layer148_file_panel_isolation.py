"""Late file responses cannot cross account or answer-view boundaries."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'history_order', 'selection', 'page', 'late_ack', 'locked_reply',
    'account_switch', 'old_finally', 'list_after_lock', 'list_after_switch',
    'preview_after_lock', 'history_after_lock', 'upload_after_lock',
    'download_after_lock', 'choose_race_error', 'refresh_selection', 'refresh_selection_error',
])
def test_file_panel_isolation(scenario):
    result = subprocess.run(['node', 'tests/file_panel_isolation.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
