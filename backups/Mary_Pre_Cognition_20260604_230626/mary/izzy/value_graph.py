import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALUE_GRAPH_FILE = ROOT / "value_graph.json"

def load_value_graph():
    with open(VALUE_GRAPH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def list_core_values():
    graph = load_value_graph()
    return graph.get("core_values", [])

def top_values(limit=5):
    values = list_core_values()
    return sorted(
        values,
        key=lambda x: x.get("strength", 0),
        reverse=True
    )[:limit]

def explain_value(value_name):
    values = list_core_values()
    for value in values:
        if value.get("value", "").lower() == value_name.lower():
            return value
    return None

if __name__ == "__main__":
    print()
    print("=== IZZY VALUE GRAPH v0.1 ===")
    print()

    for value in top_values(10):
        print(f"{value['value']} ({value['strength']})")
        print("Children:", ", ".join(value.get("children", [])))
        print("Evidence:")
        for item in value.get("evidence", []):
            print(f" - {item}")
        print("-" * 50)
