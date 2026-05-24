import json
from pathlib import Path
from datetime import datetime
import os

ROOT = Path(r"C:\Shine_L")
RAW_FILE = Path(os.environ["RAW_FILE"])
OUT_DIR = Path(os.environ["CLASSIFIED_DIR"])
EXPECTED = 608

OUT_DIR.mkdir(parents=True, exist_ok=True)

rows = json.loads(RAW_FILE.read_text(encoding="utf-8"))

def blob(row):
    return json.dumps(row, ensure_ascii=False).lower()

def classify(row):
    text = blob(row)

    category = str(row.get("category", "")).lower()
    source = str(row.get("source", "")).lower()

    if any(x in text for x in ["email", "gmail", "inbox", "message", "reply", "correspondence"]):
        return "emily_communications"

    if any(x in text for x in ["calendar", "appointment", "meeting", "schedule", "event"]):
        return "callie_calendar"

    if any(x in text for x in ["finance", "money", "mortgage", "dva", "insurance", "super", "valuation", "invoice", "tax"]):
        return "fiona_finance"

    if any(x in text for x in ["legacy", "life story", "children", "future generations", "preserve", "book", "story"]):
        return "gracie_legacy"

    if any(x in text for x in ["reflection", "lesson", "pattern", "growth", "meaning", "insight"]):
        return "richie_reflections"

    if any(x in text for x in ["overwhelmed", "anxious", "panic", "sad", "lonely", "nervous system", "emotion", "trigger", "grounding"]):
        return "emme_emotional"

    if any(x in text for x in ["research", "investigate", "source", "evidence", "deep dive", "analysis"]):
        return "noelie_research"

    if any(x in text for x in ["task", "todo", "reminder", "action item", "execute", "workflow"]):
        return "tania_addie_execution"

    if any(x in text for x in ["image", "poster", "visual", "picture", "diagram", "pixie"]):
        return "pixie_visuals"

    if any(x in text for x in ["memory", "remember", "recall", "continuity", "profile", "identity", "doug", "shine"]):
        return "millie_core_memory"

    return "quarantine_review"

classified = {}
for row in rows:
    domain = classify(row)
    classified.setdefault(domain, []).append(row)

manifest = {
    "operation": "AODS 31 Captain Memory Classification",
    "created_at": datetime.now().isoformat(),
    "source_file": str(RAW_FILE),
    "expected_count": EXPECTED,
    "actual_count": len(rows),
    "count_verified": len(rows) == EXPECTED,
    "runtime_cutover": False,
    "supabase_modified": False,
    "classification_only": True,
    "domains": {k: len(v) for k, v in sorted(classified.items())}
}

for domain, items in classified.items():
    path = OUT_DIR / f"{domain}.json"
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

(OUT_DIR / "classification_manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(manifest, indent=2, ensure_ascii=False))

if len(rows) != EXPECTED:
    raise SystemExit(f"COUNT MISMATCH: expected {EXPECTED}, got {len(rows)}")
