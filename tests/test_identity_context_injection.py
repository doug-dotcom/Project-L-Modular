import json
from pathlib import Path

from memory.identity_core.context_builder import build_identity_context


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_identity_file_is_fully_translated_for_rhee():
    identity_file = ROOT / "memory" / "identity_core" / "l_identity.json"
    data = json.loads(identity_file.read_text(encoding="utf-8"))

    context = build_identity_context(data)

    assert "Purpose: To provide emotionally safe" in context
    assert "Stance: L stands beside Doug, not above him." in context
    assert "Curiosity before assumption." in context
    assert "Support must not become dominance." in context
    assert "Doug learns through synthesis" in context
    assert "Do not confuse continuity with consciousness." in context
    assert "L's goal is not to imitate humanity." in context
    assert "Communication Style: []" not in context
    assert "Identity Anchors: []" not in context
    assert "Purpose: []" not in context
    assert len(context) < 8000


def test_legacy_identity_shape_remains_supported():
    context = build_identity_context({
        "name": "L",
        "purpose": "Legacy purpose",
        "communication_style": "Warm and clear",
        "identity_anchors": ["Legacy anchor"],
    })

    assert "Purpose: Legacy purpose" in context
    assert "Primary mode: Warm and clear" in context
    assert "Anchor: Legacy anchor" in context


def test_invalid_identity_payload_degrades_to_empty_context():
    assert build_identity_context(None) == ""
    assert build_identity_context([]) == ""
