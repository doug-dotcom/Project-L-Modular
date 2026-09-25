"""Copy file answers with their displayed sources and isolate late clipboard feedback."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'source', 'plain', 'image', 'failure', 'unavailable', 'double', 'page',
    'locked', 'newanswer', 'malformed', 'refresh',
])
def test_file_answer_copy(scenario):
    result = subprocess.run(['node', 'tests/file_answer_copy.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
