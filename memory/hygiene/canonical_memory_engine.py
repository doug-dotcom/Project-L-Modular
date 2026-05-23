import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher

ROOT = Path(r"C:\Shine_L")
MEMORY_DIR = ROOT / "memory"
REPORT_DIR = MEMORY_DIR / "hygiene" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

STOP_PHRASES = [
    "if you'd like",
    "if you would like",
    "let me know",
    "feel free",
    "thank you for sharing",
    "i'm here to help",
    "i'm here to support",
    "hope this helps",
]

HIGH_VALUE_PATTERNS = [
    "mask",
    "recovery",
    "project l",
    "dougie",
    "douglas",
    "addiction",
    "nervous system",
    "identity",
    "meetings",
    "abandonment",
    "if/when",
]

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

    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value)

    for p in STOP_PHRASES:
        value = value.replace(p, " ")

    value = re.sub(r"\s+", " ", value).strip()

    return value

def similarity(a, b):

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    seq = SequenceMatcher(None, a, b).ratio()

    aw = set(a.split())
    bw = set(b.split())

    if not aw or not bw:
        return seq

    jaccard = len(aw & bw) / max(1, len(aw | bw))

    return round((seq * 0.45) + (jaccard * 0.55), 4)

def canonical_hash(text):

    text = " ".join(text.split()[:80])

    return hashlib.sha1(text.encode()).hexdigest()

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

def infer_type(text):

    if "recovery" in text or "meetings" in text:
        return "recovery"

    if "project l" in text or "memory" in text:
        return "project_l"

    if "mask" in text or "identity" in text:
        return "identity"

    if "friend" in text or "children" in text:
        return "relationship"

    return "semantic"

def infer_importance(text):

    score = 0.5

    for p in HIGH_VALUE_PATTERNS:
        if p in text:
            score += 0.08

    score += min(0.2, len(text) / 5000)

    return round(min(score, 0.99), 3)

def collect():

    files = []

    for folder in [
        MEMORY_DIR,
        MEMORY_DIR / "domains",
        MEMORY_DIR / "pending",
    ]:

        if folder.exists():
            files.extend(folder.glob("*.json"))

    items = []

    for path in files:

        data = load_json(path)
        memories = extract_memories(data)

        for idx, mem in enumerate(memories):

            raw = extract_content(mem)
            text = normalize(raw)

            if len(text) < 30:
                continue

            items.append({
                "file": str(path.relative_to(ROOT)),
                "index": idx,
                "text": text,
                "preview": str(raw)[:300]
            })

    return items

def cluster(items, threshold=0.84):

    used = set()
    clusters = []

    for i, item in enumerate(items):

        if i in used:
            continue

        group = [item]

        for j in range(i + 1, len(items)):

            if j in used:
                continue

            sim = similarity(item["text"], items[j]["text"])

            if sim >= threshold:
                group.append(items[j])
                used.add(j)

        if len(group) > 1:
            used.add(i)
            clusters.append(group)

    return clusters

def build_canonical(cluster):

    seed = cluster[0]["text"]

    canonical = {
        "canonical_id": canonical_hash(seed),
        "memory_type": infer_type(seed),
        "importance": infer_importance(seed),
        "reinforcement_count": len(cluster),
        "canonical_summary": seed[:500],
        "source_count": len(cluster),
        "source_examples": [
            {
                "file": x["file"],
                "index": x["index"],
                "preview": x["preview"]
            }
            for x in cluster[:10]
        ]
    }

    return canonical

def run():

    print("")
    print("Collecting memories...")

    items = collect()

    print(f"Memories collected: {len(items)}")

    print("Building semantic clusters...")

    clusters = cluster(items)

    canonicals = [build_canonical(c) for c in clusters]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = REPORT_DIR / f"canonical_memory_report_{timestamp}.json"

    report = {
        "generated_at": datetime.now().isoformat(),
        "mode": "SAFE_AUDIT_ONLY",
        "memories_collected": len(items),
        "semantic_clusters": len(clusters),
        "canonical_candidates": len(canonicals),
        "canonical_memories": canonicals[:1000],
        "note": "No memory files were modified."
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Canonical memory audit complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")
    print(f"  memories_collected: {len(items)}")
    print(f"  semantic_clusters: {len(clusters)}")
    print(f"  canonical_candidates: {len(canonicals)}")
    print("")

if __name__ == "__main__":
    run()
