import os
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

CAPTAINS_DIR = ROOT / "memory" / "captains"
EXPORTS_DIR = ROOT / "memory" / "exports"
SYNC_LOG = ROOT / "memory" / "supabase_sync" / "sync_log.json"


def load_json(path, fallback):

    try:
        if not path.exists():
            return fallback

        return json.loads(
            path.read_text(encoding="utf-8")
        )

    except Exception:
        return fallback


def save_json(path, data):

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def collect_captain_entries():

    collected = []

    for json_file in CAPTAINS_DIR.rglob("*.json"):

        data = load_json(json_file, {})

        entries = data.get("entries", [])

        for item in entries:

            item["_captain_file"] = str(json_file)

            collected.append(item)

    return collected


def build_sync_manifest():

    entries = collect_captain_entries()

    manifest = {
        "operation": "AODS33 Supabase Sync Layer",
        "created_at": datetime.now().isoformat(),
        "captain_entry_count": len(entries),
        "runtime_cutover": False,
        "supabase_modified": False,
        "sync_ready": True
    }

    return manifest


def export_sync_snapshot():

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_dir = EXPORTS_DIR / f"sync_snapshot_{stamp}"

    out_dir.mkdir(parents=True, exist_ok=True)

    entries = collect_captain_entries()

    payload = {
        "created_at": datetime.now().isoformat(),
        "entry_count": len(entries),
        "entries": entries
    }

    out_file = out_dir / "captain_sync_snapshot.json"

    save_json(out_file, payload)

    manifest = build_sync_manifest()

    save_json(
        out_dir / "sync_manifest.json",
        manifest
    )

    return {
        "snapshot": str(out_file),
        "manifest": manifest
    }


def append_sync_log(event):

    log = load_json(SYNC_LOG, [])

    log.append(event)

    save_json(SYNC_LOG, log)
