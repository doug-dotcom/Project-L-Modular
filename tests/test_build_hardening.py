from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_and_ci_dependencies_are_exactly_pinned():
    for filename in ("requirements.txt", "requirements-dev.txt"):
        lines = (ROOT / filename).read_text(encoding="utf-8").splitlines()
        dependencies = [
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith(("#", "-r "))
        ]
        assert dependencies
        assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^\s]+", item) for item in dependencies)


def test_railway_context_excludes_historical_archives_and_secrets():
    patterns = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    required = {
        "FULL_BACKUPS",
        "_FULL_BACKUPS",
        "_LOCKED_RELEASE",
        "LOCKED_RELEASES",
        "MANTLE",
        "backups",
        "_smart_backups",
        "api/Backups",
        ".env",
        ".env.*",
    }
    assert required <= patterns


def test_production_python_version_is_explicit():
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11"


def test_mobile_chat_recovers_completed_long_responses():
    source = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert "request_id: requestId" in source
    assert "/chat/result/${encodeURIComponent(requestId)}" in source
    assert "L is still thinking..." in source
    assert "recoverChatResponse(requestId)" in source
    assert "element.textContent = text" in source
