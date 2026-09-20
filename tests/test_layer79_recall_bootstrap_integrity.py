import subprocess
import sys
from pathlib import Path


def test_layer79_recall_layer_chain_installs_without_degradation():
    root = Path(__file__).resolve().parents[1]
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(root)!r}); "
        "import sitecustomize"
    )
    result = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode == 0, output
    assert "RECALL LAYER INSTALL DEGRADED" not in output, output


def test_layer79_bootstrap_degradation_receipt_includes_source_location():
    root = Path(__file__).resolve().parents[1]
    source = (root / "sitecustomize.py").read_text(encoding="utf-8")

    assert "RECALL LAYER INSTALL DEGRADED" in source
    assert "source=" in source
    assert "_source_line" in source
