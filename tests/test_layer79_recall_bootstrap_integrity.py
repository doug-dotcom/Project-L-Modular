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


def test_layer79_cold_start_without_rhee_skips_dependent_layers_cleanly():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import builtins
import sys

root = sys.argv[1]
sys.path.insert(0, root)

original_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "agents.rhee.rhee_v3":
        raise ModuleNotFoundError("simulated early-start Rhee unavailability")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import
import sitecustomize
print("cold_start_ok")
'''
    result = subprocess.run(
        [sys.executable, "-S", "-c", script, str(root)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode == 0, output
    assert "cold_start_ok" in output
    assert "RECALL LAYER INSTALL DEGRADED" not in output
    assert "NameError" not in output


def test_layer79_bootstrap_declares_rhee_prerequisite_before_layer2_and_layer3():
    root = Path(__file__).resolve().parents[1]
    source = (root / "sitecustomize.py").read_text(encoding="utf-8")

    assert "_rhee = None" in source
    assert "_re = None" in source
    assert 'raise RuntimeError("rhee_bootstrap_unavailable")' in source
    assert "if _rhee is not None:" in source
