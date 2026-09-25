"""File requests release the UI even when transport or body reads never finish."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'upload_transport', 'upload_body', 'upload_locked', 'upload_error',
    'list_transport', 'list_body', 'preview_transport', 'preview_body',
    'history_transport', 'history_body', 'download_transport', 'download_body',
    'download_locked',
])
def test_file_request_timeout(scenario):
    result = subprocess.run(['node', 'tests/file_request_timeout.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
