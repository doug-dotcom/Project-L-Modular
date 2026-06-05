import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REL_FILE = ROOT / "relationships.json"

def load_relationships():

    if not REL_FILE.exists():
        return []

    with open(REL_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_relationships(data):

    with open(REL_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def add_relationship(source,target,relationship="related"):

    data = load_relationships()

    entry = {
        "source": source,
        "target": target,
        "relationship": relationship
    }

    data.append(entry)

    save_relationships(data)

    return entry

if __name__ == "__main__":

    result = add_relationship(
        "DVA",
        "Financial",
        "funding"
    )

    print(result)
