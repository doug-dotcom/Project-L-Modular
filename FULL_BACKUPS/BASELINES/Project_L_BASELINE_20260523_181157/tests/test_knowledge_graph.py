from services.runtime_knowledge_graph_service import (
    create_node,
    create_edge,
    graph_status,
    recent_nodes,
    recent_edges,
    search_nodes
)

print("")
print("===================================")
print("AODS 68 VALIDATION")
print("===================================")
print("")

print("INITIAL STATUS:")
print(graph_status())

print("")

runtime_node = create_node(
    label="L Runtime",
    node_type="system"
)

memory_node = create_node(
    label="Doug memory continuity",
    node_type="memory"
)

edge = create_edge(
    source_id=runtime_node["node_id"],
    target_id=memory_node["node_id"],
    relationship="tracks"
)

print("CREATED NODES:")
print(runtime_node)
print(memory_node)

print("")
print("CREATED EDGE:")
print(edge)

print("")
print("GRAPH STATUS:")
print(graph_status())

print("")
print("SEARCH RESULTS:")
print(search_nodes("Doug"))

print("")
print("RECENT NODES:")
print(recent_nodes())

print("")
print("RECENT EDGES:")
print(recent_edges())
