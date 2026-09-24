"""Keyboard dismissal must invalidate pending review work."""
import subprocess


def test_escape_closes_only_the_active_review():
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', 'escape'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
