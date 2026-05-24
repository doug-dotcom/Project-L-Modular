# ============================================================
# ADVANCED MEMORY LEARNING ENGINE
# AODS-96
# ============================================================

import json
from pathlib import Path
from datetime import datetime

ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

LEARNING_FILE = (
    ROOT
    / "memory"
    / "learning"
    / "adaptive_learning.json"
)

def load_learning():

    try:

        if not LEARNING_FILE.exists():
            return {}

        return json.loads(
            LEARNING_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:

        print(
            "LEARNING LOAD ERROR:",
            e
        )

        return {}

def save_learning(data):

    try:

        LEARNING_FILE.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    except Exception as e:

        print(
            "LEARNING SAVE ERROR:",
            e
        )

def reinforce_memory(text):

    try:

        data = load_learning()

        text_lower = str(text).lower()

        domains = {

            "family": [
                "family",
                "children",
                "kids",
                "iyla",
                "ashton",
                "luella",
                "mehlia"
            ],

            "project_l": [
                "project l",
                "memory",
                "orchestration",
                "runtime",
                "captains"
            ],

            "identity": [
                "truth",
                "continuity",
                "growth",
                "values"
            ]
        }

        for domain, triggers in domains.items():

            for trigger in triggers:

                if trigger in text_lower and len(trigger) > 4:

                    if domain not in data:

                        data[domain] = {

                            "count": 0,
                            "last_seen": "",
                            "importance": 1
                        }

                    data[domain]["count"] += 1

                    data[domain]["importance"] += 1

                    data[domain]["last_seen"] = str(
                        datetime.now()
                    )

        save_learning(data)

        return data

    except Exception as e:

        print(
            "REINFORCEMENT ERROR:",
            e
        )

        return {}

def learning_status():

    data = load_learning()

    return {

        "status": "online",

        "tracked_domains": len(data),

        "domains": list(data.keys()),

        "operation": "AODS96"
    }


