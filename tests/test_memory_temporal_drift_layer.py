from datetime import datetime, timezone

from core.cognition.memory_temporal_drift import build_memory_temporal_drift_packet


def _cue():
    return {"active": True}


def _surface(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def test_recent_memory_can_remain_surfaceable():
    packet = build_memory_temporal_drift_packet(
        "This feels like the same project problem again.",
        _cue(),
        _surface(),
        {"evidence": [{
            "source": "memory_general:1",
            "quote_source": "On the project, testing one change at a time helped.",
            "role": "user",
            "created_at": "2026-08-01T00:00:00+00:00",
        }]},
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["status"] == "temporally_usable"


def test_newer_change_evidence_downgrades_old_memory():
    packet = build_memory_temporal_drift_packet(
        "This project issue feels like before.",
        _cue(),
        _surface(),
        {"evidence": [
            {
                "source": "memory_general:1",
                "quote_source": "For this project issue, restarting the service helped.",
                "role": "user",
                "created_at": "2025-05-01T00:00:00+00:00",
            },
            {
                "source": "memory_general:2",
                "quote_source": "The project issue changed; now restarting no longer helps and we use a different fix.",
                "role": "user",
                "created_at": "2026-08-20T00:00:00+00:00",
            },
        ]},
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["material_update_found"] is True


def test_very_old_unrevalidated_memory_is_kept_historical():
    packet = build_memory_temporal_drift_packet(
        "This feels similar to an old project issue.",
        _cue(),
        _surface(),
        {"evidence": [{
            "source": "memory_general:1",
            "quote_source": "A project lesson that helped at the time.",
            "role": "user",
            "created_at": "2020-01-01T00:00:00+00:00",
        }]},
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert packet["decision"] == "silent"
    assert packet["status"] == "stale_unrevalidated"


def test_prior_silent_permission_cannot_be_upgraded():
    packet = build_memory_temporal_drift_packet(
        "This feels familiar.",
        _cue(),
        {"active": True, "decision": "silent", "surface_allowed": False, "source": None},
        {"evidence": []},
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_temporal_drift_packet("Hello", {"active": False}, {}, {})
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
