import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

MEMORY_DIR = ROOT / "memory"
HYGIENE_REPORTS = MEMORY_DIR / "hygiene" / "reports"
ACTIVE_DIR = MEMORY_DIR / "active"

ACTIVE_DIR.mkdir(parents=True, exist_ok=True)

def newest_report(pattern):

    files = sorted(
        HYGIENE_REPORTS.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        return None

    return files[0]

def load_json(path):

    if not path:
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def normalize(text):

    if text is None:
        return ""

    if isinstance(text, dict):
        text = json.dumps(text, ensure_ascii=False)

    elif isinstance(text, list):
        text = " ".join([str(x) for x in text])

    else:
        text = str(text)

    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()

    return text

def build_active_index():

    salience_report = load_json(
        newest_report("salience_report_*.json")
    )

    type_report = load_json(
        newest_report("memory_type_report_*.json")
    )

    canonical_report = load_json(
        newest_report("canonical_memory_report_*.json")
    )

    active = {
        "generated_at": datetime.now().isoformat(),
        "critical_memories": [],
        "high_memories": [],
        "identity_core": [],
        "relationship_core": [],
        "recovery_core": [],
        "project_l_core": [],
        "active_working_set": [],
    }

    # --------------------------------------------------------
    # SALIENCE
    # --------------------------------------------------------

    if salience_report:

        for r in salience_report.get("results", []):

            band = r.get("band")

            item = {
                "file": r.get("file"),
                "index": r.get("index"),
                "score": r.get("salience_score"),
                "preview": r.get("preview"),
            }

            if band == "critical":
                active["critical_memories"].append(item)

            elif band == "high":
                active["high_memories"].append(item)

    # --------------------------------------------------------
    # TYPES
    # --------------------------------------------------------

    if type_report:

        for r in type_report.get("results", []):

            t = r.get("memory_type")

            item = {
                "file": r.get("file"),
                "index": r.get("index"),
                "preview": r.get("preview"),
            }

            if t == "identity":
                active["identity_core"].append(item)

            elif t == "relationship":
                active["relationship_core"].append(item)

            elif t == "recovery":
                active["recovery_core"].append(item)

            elif t == "project_l":
                active["project_l_core"].append(item)

    # --------------------------------------------------------
    # CANONICAL
    # --------------------------------------------------------

    if canonical_report:

        for c in canonical_report.get(
            "canonical_memories",
            []
        ):

            if c.get("importance", 0) >= 0.75:

                active["active_working_set"].append({
                    "canonical_id": c.get("canonical_id"),
                    "memory_type": c.get("memory_type"),
                    "importance": c.get("importance"),
                    "reinforcement_count": c.get("reinforcement_count"),
                    "summary": c.get("canonical_summary"),
                })

    # --------------------------------------------------------
    # LIMITS
    # --------------------------------------------------------

    active["critical_memories"] = active["critical_memories"][:250]
    active["high_memories"] = active["high_memories"][:250]

    active["identity_core"] = active["identity_core"][:150]
    active["relationship_core"] = active["relationship_core"][:150]
    active["recovery_core"] = active["recovery_core"][:150]
    active["project_l_core"] = active["project_l_core"][:150]

    active["active_working_set"] = active["active_working_set"][:300]

    return active

def run():

    print("")
    print("Building active cognition index...")

    active = build_active_index()

    out_path = ACTIVE_DIR / "active_cognition_index.json"

    out_path.write_text(
        json.dumps(active, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Active cognition index complete.")
    print(f"Index written to: {out_path}")
    print("")

    print("Summary:")
    print(f"  critical_memories: {len(active['critical_memories'])}")
    print(f"  high_memories: {len(active['high_memories'])}")
    print(f"  identity_core: {len(active['identity_core'])}")
    print(f"  relationship_core: {len(active['relationship_core'])}")
    print(f"  recovery_core: {len(active['recovery_core'])}")
    print(f"  project_l_core: {len(active['project_l_core'])}")
    print(f"  active_working_set: {len(active['active_working_set'])}")
    print("")

if __name__ == "__main__":
    run()
