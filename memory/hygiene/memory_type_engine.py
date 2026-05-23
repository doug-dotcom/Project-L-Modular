import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")
MEMORY_DIR = ROOT / "memory"
REPORT_DIR = MEMORY_DIR / "hygiene" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

TYPE_RULES = {

    "identity": [
        "i am",
        "identity",
        "mask",
        "doug",
        "dougie",
        "douglas",
        "values",
        "who i am",
        "authentic",
    ],

    "relationship": [
        "friend",
        "best friend",
        "wife",
        "partner",
        "children",
        "daughter",
        "son",
        "leah",
        "steve",
        "wayne",
        "pauline",
        "family",
    ],

    "recovery": [
        "recovery",
        "aa",
        "na",
        "steps",
        "sobriety",
        "addiction",
        "meetings",
        "sponsor",
        "alcohol",
    ],

    "psychology": [
        "schema",
        "trauma",
        "nervous system",
        "polyvagal",
        "attachment",
        "emotional regulation",
        "psychology",
        "mask",
        "abandonment",
    ],

    "project_l": [
        "project l",
        "memory",
        "cognition",
        "semantic",
        "retrieval",
        "hydration",
        "assistant",
        "ai",
        "shine",
        "brittany",
    ],

    "episodic": [
        "yesterday",
        "today",
        "this morning",
        "last night",
        "went to",
        "i spoke",
        "i felt",
    ],

    "sport": [
        "hockey",
        "netball",
        "sport",
        "kedron",
    ],

    "military": [
        "army",
        "east timor",
        "deployment",
        "military",
    ],

    "assistant_meta": [
        "i'm here to help",
        "let me know",
        "thank you for sharing",
        "i appreciate your feedback",
        "i will continue",
        "as an ai",
    ],
}

def normalize(value):

    if value is None:
        return ""

    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)

    elif isinstance(value, list):
        value = " ".join([str(x) for x in value])

    else:
        value = str(value)

    value = value.lower()
    value = re.sub(r"\s+", " ", value).strip()

    return value

def detect_type(text):

    scores = defaultdict(int)

    for mem_type, rules in TYPE_RULES.items():
        for r in rules:
            if r in text:
                scores[mem_type] += 1

    if not scores:
        return "unclassified"

    return max(scores, key=scores.get)

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def extract_memories(data):

    if isinstance(data, dict) and isinstance(data.get("memories"), list):
        return data["memories"]

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for k in ["items", "data", "queue", "pending"]:
            if isinstance(data.get(k), list):
                return data[k]

    return []

def extract_content(mem):

    if isinstance(mem, dict):

        for k in [
            "content",
            "text",
            "summary",
            "memory",
            "message"
        ]:
            if k in mem:
                return mem.get(k)

    return mem

def run():

    files = []

    for folder in [
        MEMORY_DIR,
        MEMORY_DIR / "domains",
        MEMORY_DIR / "pending",
    ]:

        if folder.exists():
            files.extend(folder.glob("*.json"))

    results = []
    totals = defaultdict(int)

    for path in files:

        data = load_json(path)
        memories = extract_memories(data)

        for idx, mem in enumerate(memories):

            raw = extract_content(mem)
            text = normalize(raw)

            if len(text) < 10:
                continue

            mem_type = detect_type(text)

            totals[mem_type] += 1

            results.append({
                "file": str(path.relative_to(ROOT)),
                "index": idx,
                "memory_type": mem_type,
                "preview": text[:220]
            })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = REPORT_DIR / f"memory_type_report_{timestamp}.json"

    report = {
        "generated_at": datetime.now().isoformat(),
        "mode": "SAFE_AUDIT_ONLY",
        "memory_count": len(results),
        "type_totals": dict(totals),
        "results": results[:5000],
        "results_note": "limited to first 5000 rows for readability"
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Memory type audit complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k, v in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()
