"""Optional voice callbacks cannot interrupt typed submission or delivery."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['draft', 'reply', 'both', 'uncertain'])
def test_voice_callback_isolation(scenario):
    result = subprocess.run(['node', 'tests/voice_callback_isolation.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
