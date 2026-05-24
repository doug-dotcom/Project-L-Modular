# =====================================================
# runtime_graph_ingest_service.py
# AODS 68
# =====================================================

from services.runtime_knowledge_graph_service import (
    create_node,
    create_edge
)

def ingest_memory_event(text):

    memory_node = create_node(
        label=text,
        node_type="memory"
    )

    system_node = create_node(
        label="L Runtime",
        node_type="system"
    )

    relationship = create_edge(
        source_id=system_node["node_id"],
        target_id=memory_node["node_id"],
        relationship="recorded_memory"
    )

    return {
        "memory_node": memory_node,
        "system_node": system_node,
        "relationship": relationship
    }
