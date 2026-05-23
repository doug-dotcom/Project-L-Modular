import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(r"C:\Shine_L")
MEMORY_DIR = ROOT / "memory"
REPORT_DIR = MEMORY_DIR / "hygiene" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

HIGH_IMPORTANCE = [
    "children",
    "ashton",
    "iyla",
    "luella",
    "mehlia",
    "recovery",
    "project l",
    "mask",
    "dougie",
    "douglas",
    "identity",
    "abandonment",
    "trauma",
    "pauline",
    "meetings",
    "army",
]

MEDIUM_IMPORTANCE = [
    "hockey",
    "memory",
    "shine",
    "psychology",
    "emotion",
    "fear",
    "adhd",
    "relationship",
]

LOW_IMPORTANCE = [
    "thank you",
    "let me know",
    "hope this helps",
    "certainly",
    "absolutely",
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
    value = re.sub(r"\s+", " ", value).strip()

    return value

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

def calculate_salience(text):

    score = 0.10

    for kw in HIGH_IMPORTANCE:
        if kw in text:
            score += 0.18

    for kw in MEDIUM_IMPORTANCE:
        if kw in text:
            score += 0.08

    for kw in LOW_IMPORTANCE:
        if kw in text:
            score -= 0.15

    # emotional depth
    emotional_terms = [
        "fear",
        "pain",
        "grief",
        "recovery",
        "identity",
        "abandonment",
        "connection",
        "love",
        "children",
    ]

    emotional_hits = sum(
        1 for t in emotional_terms if t in text
    )

    score += emotional_hits * 0.04

    # length weighting
    score += min(0.12, len(text) / 4000)

    score = max(0.01, min(score, 0.99))

    return round(score, 3)

def salience_band(score):

    if score >= 0.75:
        return "critical"

    if score >= 0.55:
        return "high"

    if score >= 0.35:
        return "medium"

    return "low"

def estimate_half_life(score):

    if score >= 0.75:
        return "persistent"

    if score >= 0.55:
        return "long_term"

    if score >= 0.35:
        return "medium_term"

    return "short_term"

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

    bands = defaultdict(int)

    for path in files:

        data = load_json(path)
        memories = extract_memories(data)

        for idx, mem in enumerate(memories):

            raw = extract_content(mem)
            text = normalize(raw)

            if len(text) < 10:
                continue

            score = calculate_salience(text)

            band = salience_band(score)

            half_life = estimate_half_life(score)

            bands[band] += 1

            results.append({
                "file": str(path.relative_to(ROOT)),
                "index": idx,
                "salience_score": score,
                "band": band,
                "half_life": half_life,
                "preview": text[:250]
            })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = REPORT_DIR / f"salience_report_{timestamp}.json"

    report = {
        "generated_at": datetime.now().isoformat(),
        "mode": "SAFE_AUDIT_ONLY",
        "memory_count": len(results),
        "band_totals": dict(bands),
        "results": results[:5000],
        "results_note": "limited to first 5000 rows for readability"
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Salience audit complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k, v in sorted(
        bands.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()
