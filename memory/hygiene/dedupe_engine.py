import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "memory"
REPORT_DIR = MEMORY_DIR / "hygiene" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

STOP_PHRASES = [
    "if you'd like",
    "if you would like",
    "let me know",
    "feel free",
    "i'm here to help",
    "i'm here to support",
    "hope this helps",
    "thank you for sharing",
    "thank you for your feedback",
]

def normalize_text(value) -> str:
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
    value = re.sub(r"\s+", " ", value).strip()

    for phrase in STOP_PHRASES:
        value = value.replace(phrase, " ")

    value = re.sub(r"\s+", " ", value).strip()
    return value

def compact_signature(text: str) -> str:
    words = text.split()
    words = [w for w in words if len(w) > 2]
    return " ".join(words[:80])

def hash_signature(text: str) -> str:
    sig = compact_signature(text)
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()

def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    a_words = set(a.split())
    b_words = set(b.split())

    if not a_words or not b_words:
        return 0.0

    jaccard = len(a_words & b_words) / max(1, len(a_words | b_words))
    seq = SequenceMatcher(None, a, b).ratio()

    return round((jaccard * 0.65) + (seq * 0.35), 4)

def load_json(path: Path):
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
        for key in ["items", "data", "queue", "pending"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []

def extract_content(mem):
    if isinstance(mem, dict):
        for key in ["content", "text", "summary", "memory", "message"]:
            if key in mem:
                return mem.get(key)
        return mem
    return mem

def collect_all_memories():
    targets = []

    for folder in [
        MEMORY_DIR / "domains",
        MEMORY_DIR / "pending",
        MEMORY_DIR
    ]:
        if folder.exists():
            targets.extend(folder.glob("*.json"))

    seen_files = set()
    all_items = []

    for path in targets:
        resolved = path.resolve()
        if resolved in seen_files:
            continue

        seen_files.add(resolved)
        data = load_json(path)
        memories = extract_memories(data)

        for idx, mem in enumerate(memories):
            raw = extract_content(mem)
            norm = normalize_text(raw)

            if len(norm) < 20:
                continue

            all_items.append({
                "file": str(path.relative_to(ROOT)),
                "index": idx,
                "normalized": norm,
                "preview": str(raw)[:300].replace("\n", " "),
                "signature": compact_signature(norm),
                "hash": hash_signature(norm),
            })

    return all_items

def exact_duplicate_clusters(items):
    buckets = defaultdict(list)

    for item in items:
        buckets[item["hash"]].append(item)

    return [cluster for cluster in buckets.values() if len(cluster) > 1]

def near_duplicate_clusters(items, threshold=0.82, max_items=4000):
    limited = items[:max_items]
    used = set()
    clusters = []

    for i, item in enumerate(limited):
        if i in used:
            continue

        cluster = [item]

        for j in range(i + 1, len(limited)):
            if j in used:
                continue

            score = similarity(item["signature"], limited[j]["signature"])

            if score >= threshold:
                cluster.append(limited[j])
                used.add(j)

        if len(cluster) > 1:
            used.add(i)
            clusters.append(cluster)

    return clusters

def summarize_cluster(cluster):
    seed = cluster[0]
    return {
        "cluster_size": len(cluster),
        "canonical_preview": seed["preview"],
        "suggested_action": "merge_into_one_canonical_memory",
        "reinforcement_count": len(cluster),
        "items": [
            {
                "file": x["file"],
                "index": x["index"],
                "preview": x["preview"],
            }
            for x in cluster[:25]
        ],
        "truncated_items": max(0, len(cluster) - 25)
    }

def run_dedupe():
    print("")
    print("Collecting memories...")
    items = collect_all_memories()

    print(f"Memories collected: {len(items)}")
    print("Detecting exact duplicates...")
    exact = exact_duplicate_clusters(items)

    print("Detecting near duplicates...")
    near = near_duplicate_clusters(items)

    exact_reports = [summarize_cluster(c) for c in exact]
    near_reports = [summarize_cluster(c) for c in near]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"semantic_dedupe_report_{timestamp}.json"

    report = {
        "generated_at": datetime.now().isoformat(),
        "mode": "SAFE_AUDIT_ONLY",
        "note": "This report does not modify memory files.",
        "memories_collected": len(items),
        "exact_duplicate_clusters": len(exact_reports),
        "near_duplicate_clusters": len(near_reports),
        "estimated_exact_duplicate_items": sum(c["cluster_size"] for c in exact_reports),
        "estimated_near_duplicate_items": sum(c["cluster_size"] for c in near_reports),
        "exact_clusters": exact_reports[:200],
        "near_clusters": near_reports[:200],
        "cluster_report_limit_note": "Only first 200 clusters of each type are included to keep report readable."
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("")
    print("Semantic dedupe audit complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")
    print(f"  memories_collected: {len(items)}")
    print(f"  exact_duplicate_clusters: {len(exact_reports)}")
    print(f"  near_duplicate_clusters: {len(near_reports)}")
    print(f"  estimated_exact_duplicate_items: {report['estimated_exact_duplicate_items']}")
    print(f"  estimated_near_duplicate_items: {report['estimated_near_duplicate_items']}")
    print("")

    return report

if __name__ == "__main__":
    run_dedupe()
