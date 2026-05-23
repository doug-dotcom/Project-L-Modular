import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

TRAIN_DIR = ROOT / "memory" / "training"
OUT_FILE = TRAIN_DIR / "soft_training_state.json"

REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

PATTERNS = {

    "project_l": [
        "project l",
        "memory",
        "cognition",
        "runtime",
        "continuity"
    ],

    "identity": [
        "identity",
        "mask",
        "meaning",
        "purpose",
        "self worth"
    ],

    "recovery": [
        "recovery",
        "healing",
        "meetings",
        "growth",
        "regulation"
    ],

    "emotion": [
        "fear",
        "hope",
        "love",
        "stress",
        "connection"
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

    return re.sub(
        r"\s+",
        " ",
        str(text).lower()
    ).strip()

def load_training_text():

    files = list(TRAIN_DIR.glob("*.txt"))

    collected = []

    for file in files:

        try:

            text = file.read_text(
                encoding="utf-8"
            )

            collected.append(text)

        except:
            pass

    return collected

def analyze(texts):

    reinforcement = defaultdict(int)

    for text in texts:

        lowered = normalize(text)

        for category, patterns in PATTERNS.items():

            for p in patterns:

                if p in lowered:
                    reinforcement[category] += 1

    return reinforcement

def run():

    print("")
    print("Loading training reflections...")

    texts = load_training_text()

    print(f"Training files loaded: {len(texts)}")

    reinforcement = analyze(texts)

    output = {
        "created_at": str(datetime.utcnow()),
        "training_reinforcement": reinforcement
    }

    OUT_FILE.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"soft_training_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print("")
    print("Soft training complete.")
    print(f"Training state written to: {OUT_FILE}")
    print(f"Report written to: {report_path}")

    print("")
    print("Training Summary:")

    for k, v in reinforcement.items():
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()

