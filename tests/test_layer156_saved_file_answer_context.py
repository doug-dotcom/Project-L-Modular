"""Saved file answers reopen their confirmed original file/page context before display."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'align', 'missing', 'pagegone', 'malformed', 'pagechange', 'account', 'legacy',
])
def test_saved_file_answer_context(scenario):
    result = subprocess.run(
        ['node', 'tests/saved_file_answer_context.test.cjs', scenario],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
