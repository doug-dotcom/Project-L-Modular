from memory.retrieval.provenance import (
    annotate_memory_provenance,
    build_raw_role_index,
    memory_source_role,
    provenance_adjustment,
    provenance_trust_rank,
)


def test_raw_id_link_is_authoritative_provenance():
    index = build_raw_role_index([
        {"id": 101, "role": "user"},
        {"id": 102, "role": "assistant"},
    ])
    memory = {"raw_id": "101", "role": "assistant", "content": "A fact"}

    annotate_memory_provenance(memory, index)

    assert memory_source_role(memory) == "user"
    assert memory["_provenance_evidence"] == "raw_catchall"


def test_local_role_and_unlinked_memory_have_safe_fallbacks():
    local = annotate_memory_provenance({"role": "assistant"}, {})
    unlinked = annotate_memory_provenance({"content": "Research evidence"}, {})

    assert memory_source_role(local) == "assistant"
    assert local["_provenance_evidence"] == "embedded_role"
    assert memory_source_role(unlinked) == "unknown"
    assert unlinked["_provenance_evidence"] == "unlinked"


def test_weighting_prioritises_doug_without_discarding_secondary_evidence():
    assert provenance_adjustment("user") == 120
    assert provenance_adjustment("assistant") == -40
    assert provenance_adjustment("unknown") == 0
    assert provenance_adjustment("user", raw=True) == 80
    assert provenance_adjustment("assistant", raw=True) == -20
    assert provenance_trust_rank({"_source_role": "user"}) > provenance_trust_rank({"_source_role": "assistant"})
