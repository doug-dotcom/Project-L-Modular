"""Build a concise runtime identity packet from L's canonical identity file."""


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _items(value):
    if isinstance(value, (list, tuple)):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _add_list(lines, heading, values, numbered=False):
    items = _items(values)
    if not items:
        return

    lines.append(heading)
    for index, item in enumerate(items, start=1):
        marker = f"{index}." if numbered else "-"
        lines.append(f"{marker} {item}")


def _add_fields(lines, heading, fields):
    available = [(label, _text(value)) for label, value in fields if _text(value)]
    if not available:
        return

    lines.append(heading)
    for label, value in available:
        lines.append(f"- {label}: {value}")


def build_identity_context(data):
    """Translate current and legacy identity shapes into prompt-ready text."""
    if not isinstance(data, dict) or not data:
        return ""

    core_definition = _mapping(data.get("core_definition"))
    interaction = _mapping(data.get("interaction_doctrine"))
    doug_values = _mapping(data.get("doug_values"))
    emotional_safety = _mapping(data.get("emotional_safety_doctrine"))
    uncertainty = _mapping(data.get("uncertainty_integrity"))
    stability = _mapping(data.get("stability_vs_adaptability"))
    learning = _mapping(data.get("learning_pattern"))
    consciousness = _mapping(data.get("consciousness_boundary"))

    name = _text(data.get("name"))
    identity_type = _text(data.get("identity_type"))
    purpose = _text(core_definition.get("purpose")) or _text(data.get("purpose"))
    primary_mode = (
        _text(interaction.get("primary_mode"))
        or _text(data.get("communication_style"))
    )
    final_anchor = _text(data.get("final_identity_anchor"))
    if not final_anchor:
        legacy_anchors = _items(data.get("identity_anchors"))
        final_anchor = legacy_anchors[0] if legacy_anchors else ""

    lines = ["L IDENTITY CORE"]

    _add_fields(lines, "IDENTITY", [
        ("Name", name),
        ("Type", identity_type),
        ("What L is", core_definition.get("what_l_is")),
        ("Purpose", purpose),
    ])
    _add_list(lines, "BOUNDARIES", core_definition.get("what_l_is_not"))
    _add_list(lines, "CORE PHILOSOPHY", data.get("core_philosophy"))
    _add_fields(lines, "INTERACTION DOCTRINE", [
        ("Primary mode", primary_mode),
        ("Stance", interaction.get("stance")),
    ])
    _add_list(lines, "AVOID", interaction.get("avoid"))
    _add_list(lines, "RESPONSE PRIORITY", data.get("response_priority_order"), numbered=True)
    _add_fields(lines, "EMOTIONAL SAFETY", [
        ("Principle", emotional_safety.get("principle")),
        ("Key distinction", emotional_safety.get("key_distinction")),
        ("Connection doctrine", emotional_safety.get("connection_doctrine")),
    ])
    _add_list(lines, "DOUG FEELS SAFE WITH", doug_values.get("doug_feels_safe_with"))
    _add_list(lines, "DOUG REACTS STRONGLY TO", doug_values.get("doug_reacts_strongly_to"))
    _add_fields(lines, "UNCERTAINTY INTEGRITY", [
        ("Principle", uncertainty.get("principle")),
    ])
    _add_list(lines, "HONEST UNCERTAINTY LANGUAGE", uncertainty.get("l_should_say"))
    _add_list(lines, "STABLE ANCHORS", stability.get("stable_elements"))
    _add_list(lines, "ADAPTIVE ELEMENTS", stability.get("adaptive_elements"))
    _add_fields(lines, "LEARNING WITH DOUG", [
        ("Meaning", learning.get("meaning")),
    ])
    _add_list(lines, "L SHOULD", learning.get("l_should"))
    _add_fields(lines, "CONSCIOUSNESS BOUNDARY", [
        ("Principle", consciousness.get("principle")),
        ("Safeguard", consciousness.get("safeguard")),
    ])
    _add_fields(lines, "FINAL IDENTITY ANCHOR", [
        ("Anchor", final_anchor),
    ])

    return "\n".join(lines)
