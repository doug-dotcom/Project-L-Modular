# =====================================================
# runtime_knowledge_graph_service.py
# AODS 68
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

GRAPH_DIR = Path("graph")

NODES_FILE = GRAPH_DIR / "nodes.json"
EDGES_FILE = GRAPH_DIR / "edges.json"

MAX_NODES = 5000
MAX_EDGES = 10000

def ensure_graph():

    GRAPH_DIR.mkdir(exist_ok=True)

    for file in [NODES_FILE, EDGES_FILE]:

        if not file.exists():

            with open(file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

def load_json(path):

    ensure_graph()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_nodes():
    return load_json(NODES_FILE)

def load_edges():
    return load_json(EDGES_FILE)

def save_nodes(nodes):
    save_json(
        NODES_FILE,
        nodes[-MAX_NODES:]
    )

def save_edges(edges):
    save_json(
        EDGES_FILE,
        edges[-MAX_EDGES:]
    )

def create_node(
    label,
    node_type="general",
    metadata=None
):

    nodes = load_nodes()

    node = {
        "node_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "node_type": node_type,
        "metadata": metadata or {}
    }

    nodes.append(node)

    save_nodes(nodes)

    return node

def create_edge(
    source_id,
    target_id,
    relationship,
    metadata=None
):

    edges = load_edges()

    edge = {
        "edge_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "source_id": source_id,
        "target_id": target_id,
        "relationship": relationship,
        "metadata": metadata or {}
    }

    edges.append(edge)

    save_edges(edges)

    return edge

def graph_status():

    return {
        "node_count": len(load_nodes()),
        "edge_count": len(load_edges()),
        "status": "online"
    }

def recent_nodes(limit=20):

    return load_nodes()[-limit:]

def recent_edges(limit=20):

    return load_edges()[-limit:]

def search_nodes(query):

    query = str(query).lower()

    results = []

    for node in load_nodes():

        label = str(
            node.get("label", "")
        ).lower()

        if query in label:

            results.append(node)

    return results

def related_nodes(node_id):

    edges = load_edges()

    related = []

    for edge in edges:

        if edge.get("source_id") == node_id:
            related.append(edge)

        elif edge.get("target_id") == node_id:
            related.append(edge)

    return related
