import os
import json
import hashlib
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")
ENV_PATH = ROOT / ".env"
EXPORT_DIR = Path(os.environ.get("SHINE_EXPORT_DIR"))
EXPECTED_COUNT = int(os.environ.get("EXPECTED_COUNT", "608"))

def load_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env(ENV_PATH)

url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_PROJECT_URL")
key = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)

if not url or not key:
    raise SystemExit("Missing SUPABASE_URL and/or SUPABASE key in .env")

base = url.rstrip("/")
table_url = f"{base}/rest/v1/memories?select=*&order=created_at.asc"

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Accept": "application/json",
}

all_rows = []
offset = 0
limit = 1000

while True:
    req = urllib.request.Request(
        table_url,
        headers={**headers, "Range": f"{offset}-{offset + limit - 1}"},
        method="GET",
    )

    with urllib.request.urlopen(req) as response:
        batch = json.loads(response.read().decode("utf-8"))

    if not batch:
        break

    all_rows.extend(batch)

    if len(batch) < limit:
        break

    offset += limit

EXPORT_DIR.mkdir(parents=True, exist_ok=True)

raw_path = EXPORT_DIR / "supabase_memories_raw.json"
pretty_path = EXPORT_DIR / "supabase_memories_pretty.json"
manifest_path = EXPORT_DIR / "export_manifest.json"

raw_text = json.dumps(all_rows, ensure_ascii=False, separators=(",", ":"))
pretty_text = json.dumps(all_rows, indent=2, ensure_ascii=False)

raw_path.write_text(raw_text, encoding="utf-8")
pretty_path.write_text(pretty_text, encoding="utf-8")

sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

manifest = {
    "operation": "AODS 10 Supabase Export Protection",
    "exported_at": datetime.now().isoformat(),
    "table": "public.memories",
    "expected_count": EXPECTED_COUNT,
    "actual_count": len(all_rows),
    "count_verified": len(all_rows) == EXPECTED_COUNT,
    "sha256": sha256,
    "raw_file": str(raw_path),
    "pretty_file": str(pretty_path),
    "runtime_cutover": False,
    "supabase_modified": False,
    "doctrine": "Archive protected before migration. No memory deletion. No live cutover."
}

manifest_path.write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(manifest, indent=2, ensure_ascii=False))

if len(all_rows) != EXPECTED_COUNT:
    raise SystemExit(f"COUNT MISMATCH: expected {EXPECTED_COUNT}, got {len(all_rows)}")
