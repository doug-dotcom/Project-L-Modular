import json
from pathlib import Path
from datetime import datetime
import os

ROOT = Path(r"C:\Shine_L")
CLASSIFIED_DIR = Path(os.environ["CLASSIFIED_DIR"])
EXPECTED = 608

captain_map = {
    "emily_communications": ("emily", "communications.json"),
    "callie_calendar": ("callie", "calendar.json"),
    "fiona_finance": ("fiona", "finance.json"),
    "gracie_legacy": ("gracie", "legacy.json"),
    "richie_reflections": ("richie", "reflections.json"),
    "emme_emotional": ("emme", "emotional_state.json"),
    "noelie_research": ("noelie", "research.json"),
    "tania_addie_execution": ("tania", "tasks.json"),
    "pixie_visuals": ("pixie", "visuals.json"),
    "millie_core_memory": ("millie", "memory_core.json"),
    "quarantine_review": ("..", "quarantine/review_required.json"),
}

written_total = 0
outputs = {}

for domain, target in captain_map.items():
    src = CLASSIFIED_DIR / f"{domain}.json"

    if src.exists():
        entries = json.loads(src.read_text(encoding="utf-8"))
    else:
        entries = []

    captain, filename = target

    if captain == "..":
        out_path = ROOT / "memory" / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        captain_name = "Quarantine"
        rank = "Review"
    else:
        out_path = ROOT / "memory" / "captains" / captain / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        captain_name = captain.capitalize()
        rank = "Captain"

    payload = {
        "captain": captain_name,
        "rank": rank,
        "domain": domain,
        "source": "supabase_export_classified",
        "runtime_active": False,
        "supabase_sync": True,
        "populated_by": "AODS32",
        "populated_at": datetime.now().isoformat(),
        "entry_count": len(entries),
        "entries": entries
    }

    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    written_total += len(entries)
    outputs[domain] = {
        "target": str(out_path),
        "count": len(entries)
    }

manifest = {
    "operation": "AODS 32 Local JSON Population",
    "created_at": datetime.now().isoformat(),
    "classified_dir": str(CLASSIFIED_DIR),
    "expected_count": EXPECTED,
    "written_total": written_total,
    "count_verified": written_total == EXPECTED,
    "runtime_cutover": False,
    "supabase_modified": False,
    "outputs": outputs
}

manifest_path = ROOT / "memory" / "indexes" / "local_json_population_manifest.json"
manifest_path.write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(manifest, indent=2, ensure_ascii=False))

if written_total != EXPECTED:
    raise SystemExit(f"COUNT MISMATCH: expected {EXPECTED}, wrote {written_total}")

