import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"

OUT_DIR = ROOT / "memory" / "compression"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

THEMES = {

    "project_l": [
        "project l",
        "memory",
        "cognition",
        "runtime",
        "architecture",
        "aods"
    ],

    "identity": [
        "identity",
        "mask",
        "meaning",
        "doug",
        "dougie",
        "douglas"
    ],

    "recovery": [
        "recovery",
        "healing",
        "meetings",
        "growth",
        "regulation"
    ],

    "fear_stress": [
        "fear",
        "stress",
        "money",
        "unsafe",
        "panic"
    ],

    "family": [
        "family",
        "kids",
        "father",
        "iyla",
        "ashton"
    ]
}

def normalize(text):

    if text is None:
        return ""

    if isinstance(text, dict):
        text = json.dumps(text, ensure_ascii=False)

    elif isinstance(text, list):
        text = " ".join([str(x) for x in text])

    else:
        text = str(text)

    return re.sub(r"\s+", " ", text).strip().lower()

def load_memories():

    memories = []

    if not DOMAIN_DIR.exists():
        return memories

    for path in DOMAIN_DIR.glob("*.json"):

        try:

            data = json.loads(
                path.read_text(encoding="utf-8")
            )

            for m in data.get("memories", []):

                text = normalize(
                    m.get("content")
                )

                if len(text) < 40:
                    continue

                memories.append(text)

        except:
            pass

    return memories

def compress(memories):

    grouped = defaultdict(list)

    for memory in memories:

        for theme, patterns in THEMES.items():

            score = 0

            for p in patterns:
                if p in memory:
                    score += 1

            if score > 0:
                grouped[theme].append(memory)

    compressed = {}

    for theme, items in grouped.items():

        compressed[theme] = {
            "memory_count": len(items),
            "compressed_summary":
                items[:5]
        }

    return compressed

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    print("")
    print("Compressing context windows...")

    compressed = compress(memories)

    output = {
        "created_at": str(datetime.utcnow()),
        "compressed_context": compressed
    }

    out_path = OUT_DIR / "compressed_context_windows.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"context_window_compression_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Context window compression complete.")
    print(f"Compression written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Compression Summary:")

    for k, v in compressed.items():

        print(
            f"  {k}: "
            f"{v['memory_count']} memories compressed"
        )

    print("")

if __name__ == "__main__":
    run()

