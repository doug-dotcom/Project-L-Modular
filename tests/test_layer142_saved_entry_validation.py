"""Invalid browser entries cannot prevent valid saved tasks being inspected."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['null', 'object', 'mixed', 'legacy', 'invalid_saved_shape', 'invalid_saved_entries'])
def test_saved_entry_validation(scenario):
    script = 'tests/saved_answer_review.test.cjs' if scenario.startswith('invalid_') else 'tests/saved_startup_validation.test.cjs'
    result = subprocess.run(['node', script, scenario], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
