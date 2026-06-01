import json

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

JOURNAL_PATH = DATA_DIR / "behaviour_journal.jsonl"
PATTERN_PATH = DATA_DIR / "behaviour_patterns.json"

BRISBANE = ZoneInfo("Australia/Brisbane")

def _now():
    return datetime.now(
        BRISBANE
    ).isoformat(timespec="seconds")

def record_behaviour_event(event):

    with open(
        JOURNAL_PATH,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                event,
                ensure_ascii=False
            ) + "\n"
        )

    return {
        "ok": True
    }

def record_behaviour_from_exchange(
    user_text,
    assistant_text=""
):

    event = {

        "created_at": _now(),

        "user_text":
            user_text[:1000],

        "assistant_text":
            assistant_text[:1000]
    }

    return record_behaviour_event(event)

def get_recent_behaviour_events(
    limit=20
):

    if not JOURNAL_PATH.exists():
        return []

    lines = JOURNAL_PATH.read_text(
        encoding="utf-8"
    ).splitlines()

    events = []

    for line in lines[-limit:]:

        try:
            events.append(
                json.loads(line)
            )
        except:
            pass

    return events

def build_behaviour_patterns(
    limit=200
):

    events = get_recent_behaviour_events(
        limit
    )

    summary = {

        "created_at": _now(),

        "events_reviewed":
            len(events),

        "status":
            "behaviour_layer_active"
    }

    PATTERN_PATH.write_text(
        json.dumps(
            summary,
            indent=2
        ),
        encoding="utf-8"
    )

    return summary

def truth_implementation_status():

    return {

        "behaviour_layer":
            True,

        "journal_exists":
            JOURNAL_PATH.exists(),

        "pattern_file":
            str(PATTERN_PATH)
    }
