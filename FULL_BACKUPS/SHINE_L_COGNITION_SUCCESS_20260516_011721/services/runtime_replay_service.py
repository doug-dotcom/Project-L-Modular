# =====================================================
# runtime_replay_service.py
# AODS 69
# =====================================================

import json
from pathlib import Path
from datetime import datetime

from services.runtime_audit_service import recent_events
from services.agent_bus_service import recent_messages
from services.runtime_knowledge_graph_service import recent_nodes, recent_edges

REPLAY_DIR = Path("replay")
REPLAY_FILE = REPLAY_DIR / "runtime_replay.json"

MAX_REPLAYS = 500

def ensure_replay():

    REPLAY_DIR.mkdir(exist_ok=True)

    if not REPLAY_FILE.exists():

        with open(REPLAY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_replays():

    ensure_replay()

    try:
        with open(REPLAY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_replays(items):

    items = items[-MAX_REPLAYS:]

    with open(REPLAY_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

def build_replay_snapshot(label="manual", limit=20):

    audit = recent_events(limit)
    bus = recent_messages(limit)
    nodes = recent_nodes(limit)
    edges = recent_edges(limit)

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "audit_events": audit,
        "bus_messages": bus,
        "graph_nodes": nodes,
        "graph_edges": edges,
        "summary": {
            "audit_count": len(audit),
            "bus_count": len(bus),
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
    }

    replays = load_replays()
    replays.append(snapshot)
    save_replays(replays)

    return snapshot

def replay_status():

    replays = load_replays()

    return {
        "replay_count": len(replays),
        "status": "online",
        "last_replay": replays[-1]["timestamp"] if replays else None
    }

def recent_replays(limit=10):

    return load_replays()[-limit:]

def replay_timeline(limit=20):

    snapshot = build_replay_snapshot(
        label="timeline",
        limit=limit
    )

    timeline = []

    for item in snapshot.get("audit_events", []):

        timeline.append({
            "time": item.get("timestamp"),
            "source": item.get("source"),
            "type": item.get("event_type"),
            "detail": item.get("payload")
        })

    for item in snapshot.get("bus_messages", []):

        timeline.append({
            "time": item.get("timestamp"),
            "source": item.get("sender"),
            "type": item.get("message_type"),
            "detail": item.get("content")
        })

    timeline = sorted(
        timeline,
        key=lambda x: str(x.get("time", ""))
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "timeline": timeline,
        "count": len(timeline)
    }

def replay_summary(limit=20):

    timeline = replay_timeline(limit)

    return {
        "timestamp": datetime.now().isoformat(),
        "event_count": timeline.get("count", 0),
        "timeline_preview": timeline.get("timeline", [])[-10:],
        "status": "summary_ready"
    }
