import agents.rhee.rhee_v3 as rhee


def test_local_domain_library_is_loaded():
    memories = rhee.load_local_memories()
    assert len(memories) > 1000
    assert any(row.get("_table") == "local_family" for row in memories)


def test_recall_works_without_explicit_trigger(monkeypatch):
    monkeypatch.setattr(rhee, "supabase", None)
    packet = rhee.build_recall_packet("How is Luella?", limit=18)
    assert packet
    assert any("luella" in rhee.row_content(row).lower() for row in packet)


def test_unrelated_high_salience_memory_is_not_returned():
    memory = {
        "content": "A completely unrelated subject",
        "importance": 100,
        "salience": 100,
        "anchor": True,
    }
    assert rhee.calculate_memory_score(memory, "How is Luella?") == 0


def test_context_packet_is_bounded_and_reports_recall(monkeypatch):
    monkeypatch.setattr(rhee, "supabase", None)
    packet = rhee.build_context_packet("How is Luella?")
    assert packet["recall_active"] is True
    assert "local_" in packet["context"]
    assert len(packet["context"]) < 50000
