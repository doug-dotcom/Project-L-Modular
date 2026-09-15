from datetime import datetime, timezone

from core.cognition.memory_relevance import build_memory_relevance_packet


NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _cue(score=0.9):
    return {
        "active": True,
        "cue": {"score": score},
    }


def _confidence(fact=True, inference=True):
    return {
        "claim_permissions": {
            "personal_fact": fact,
            "supported_inference": inference,
        }
    }


def _rhee(*rows):
    return {"recall_active": True, "evidence": list(rows)}


def test_strong_direct_match_can_surface():
    packet = build_memory_relevance_packet(
        "I feel overwhelmed about recovery again",
        _cue(),
        _rhee({
            "source": "memory_recovery:1",
            "quote_source": "Recovery meetings helped when I felt overwhelmed.",
            "role": "user",
            "created_at": "2026-09-10T00:00:00+00:00",
        }),
        _confidence(),
        now=NOW,
    )
    assert packet["decision"] == "surface"
    assert len(packet["surface"]) == 1
    assert packet["surface"][0]["source"] == "memory_recovery:1"


def test_sensitive_memory_without_direct_topic_match_stays_silent():
    packet = build_memory_relevance_packet(
        "Work has been stressful again this week",
        _cue(),
        _rhee({
            "source": "memory_health:2",
            "quote_source": "A trauma discussion included PTSD and medication history.",
            "role": "user",
            "created_at": "2026-09-10T00:00:00+00:00",
        }),
        _confidence(),
        now=NOW,
    )
    assert packet["decision"] == "silent"
    assert packet["surface"] == []
    assert packet["silent"][0]["sensitive"] is True


def test_stale_unrelated_memory_is_discarded():
    packet = build_memory_relevance_packet(
        "I feel calm about the project again",
        _cue(),
        _rhee({
            "source": "memory_relationships:3",
            "quote_source": "This old relationship status was superseded and no longer current.",
            "role": "user",
            "created_at": "2024-01-01T00:00:00+00:00",
        }),
        _confidence(),
        now=NOW,
    )
    assert packet["decision"] == "discard"
    assert packet["discard"][0]["stale_or_superseded"] is True


def test_missing_claim_permission_prevents_surface_even_with_good_match():
    packet = build_memory_relevance_packet(
        "I feel overwhelmed about recovery again",
        _cue(),
        _rhee({
            "source": "memory_recovery:4",
            "quote_source": "Recovery meetings helped when I felt overwhelmed.",
            "role": "user",
            "created_at": "2026-09-10T00:00:00+00:00",
        }),
        _confidence(fact=False, inference=False),
        now=NOW,
    )
    assert packet["surface"] == []
    assert packet["decision"] in {"silent", "discard"}


def test_surface_is_capped_at_one_memory_per_turn():
    packet = build_memory_relevance_packet(
        "I feel overwhelmed about recovery again",
        _cue(),
        _rhee(
            {
                "source": "memory_recovery:5",
                "quote_source": "Recovery meetings helped when I felt overwhelmed.",
                "role": "user",
                "created_at": "2026-09-12T00:00:00+00:00",
            },
            {
                "source": "memory_recovery:6",
                "quote_source": "Recovery routine helped when I felt overwhelmed again.",
                "role": "user",
                "created_at": "2026-09-11T00:00:00+00:00",
            },
        ),
        _confidence(),
        now=NOW,
    )
    assert len(packet["surface"]) == 1
    assert len(packet["silent"]) >= 1
    assert packet["governance"]["max_surface_memories"] == 1


def test_layer_is_inactive_for_non_associative_turns():
    packet = build_memory_relevance_packet(
        "Hello",
        {"active": False},
        {},
        {},
        now=NOW,
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
