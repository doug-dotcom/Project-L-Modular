"""Closing a navigated review must invalidate its outstanding response."""
import subprocess

def test_review_navigation_and_close_during_retrieval():
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', 'navigation'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
