"""Invalid file-question inputs preserve the draft and never submit or poll."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'blank', 'space', 'zero', 'negative', 'fraction', 'beyond', 'nan', 'infinity',
    'serverlimit', 'long', 'first', 'last', 'boundary', 'unicode', 'trimmed',
])
def test_file_question_inputs(scenario):
    result = subprocess.run(['node', 'tests/file_question_inputs.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
