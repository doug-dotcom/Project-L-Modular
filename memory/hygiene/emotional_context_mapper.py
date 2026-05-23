import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"

OUT_DIR = ROOT / "memory" / "emotion"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

EMOTION_PATTERNS = {

    "fear": [
        "fear",
        "panic",
        "unsafe",
        "stress",
        "anxiety",
        "worry"
    ],

    "hope": [
        "hope",
        "future",
        "growth",
        "dream",
        "vision"
    ],

    "connection": [
        "love",
        "family",
        "brother",
        "connection",
        "belonging"
    ],

    "identity": [
        "identity",
        "meaning",
        "mask",
        "purpose",
        "who i am"
    ],

    "recovery": [
        "recovery",
        "healing",
        "meetings",
        "growth",
        "regulation"
    ],

    "creation": [
        "project l",
        "build",
        "architecture",
        "memory",
        "cognition"
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

def map_emotions(memories):

    emotional_map = defaultdict(list)

    for memory in memories:

        for emotion, patterns in EMOTION_PATTERNS.items():

            score = 0

            for p in patterns:

                if p in memory:
                    score += 1

            if score > 0:

                emotional_map[emotion].append({
                    "emotional_strength": score,
                    "memory": memory[:500]
                })

    return emotional_map

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    print("")
    print("Mapping emotional cognition...")

    emotional_map = map_emotions(memories)

    summary = {}

    for emotion, items in emotional_map.items():

        total_strength = sum(
            x["emotional_strength"]
            for x in items
        )

        summary[emotion] = {
            "memory_count": len(items),
            "emotional_strength": total_strength
        }

    output = {
        "created_at": str(datetime.utcnow()),
        "emotional_summary": summary,
        "emotional_map": emotional_map
    }

    out_path = OUT_DIR / "emotional_context_map.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"emotional_context_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Emotional context mapping complete.")
    print(f"Emotion map written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Emotion Summary:")

    for k, v in summary.items():

        print(
            f"  {k}: "
            f"{v['memory_count']} memories | "
            f"strength {v['emotional_strength']}"
        )

    print("")

if __name__ == "__main__":
    run()

