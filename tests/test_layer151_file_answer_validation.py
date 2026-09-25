"""Unreadable file answers must not be presented as recovered or lose their handle."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'missing', 'blank', 'number', 'array', 'source', 'quotes', 'quoteitem',
    'page', 'filename', 'error', 'valid', 'failed',
])
def test_file_answer_validation(scenario):
    result = subprocess.run(['node', 'tests/file_answer_validation.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
