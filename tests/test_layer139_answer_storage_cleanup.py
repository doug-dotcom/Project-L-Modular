"""Storage cleanup failures must not hide delivered answers or cause retries."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['write', 'remove', 'uncertain', 'cleanup_failure_review'])
def test_answer_storage_cleanup(scenario):
    script = 'tests/saved_answer_review.test.cjs' if scenario == 'cleanup_failure_review' else 'tests/answer_storage_cleanup.test.cjs'
    result = subprocess.run(['node', script, scenario], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
