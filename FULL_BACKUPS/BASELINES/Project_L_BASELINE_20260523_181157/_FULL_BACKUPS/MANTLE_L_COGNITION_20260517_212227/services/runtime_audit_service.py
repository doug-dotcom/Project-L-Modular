import json
import hashlib
from pathlib import Path
from datetime import datetime

AUDIT_DIR = Path("audit")
LEDGER_FILE = AUDIT_DIR / "runtime_ledger.json"

def ensure_ledger():

    AUDIT_DIR.mkdir(exist_ok=True)

    if not LEDGER_FILE.exists():

        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_ledger():

    ensure_ledger()

    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_ledger(items):

    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

def build_hash(payload):

    raw = json.dumps(
        payload,
        sort_keys=True
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()

def record_event(
    event_type,
    source,
    payload,
    severity="normal"
):

    ledger = load_ledger()

    previous_hash = (
        ledger[-1]["event_hash"]
        if ledger else
        "GENESIS"
    )

    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "source": source,
        "severity": severity,
        "payload": payload,
        "previous_hash": previous_hash
    }

    event["event_hash"] = build_hash(event)

    ledger.append(event)

    save_ledger(ledger)

    return event

def ledger_status():

    ledger = load_ledger()

    return {
        "ledger_size": len(ledger),
        "status": "online"
    }

def recent_events(limit=25):

    ledger = load_ledger()

    return ledger[-limit:]

def validate_chain():

    ledger = load_ledger()

    previous_hash = "GENESIS"

    for event in ledger:

        stored_hash = event["event_hash"]

        check = dict(event)

        del check["event_hash"]

        recalculated = build_hash(check)

        if stored_hash != recalculated:

            return {
                "status": "invalid"
            }

        if event["previous_hash"] != previous_hash:

            return {
                "status": "chain_broken"
            }

        previous_hash = stored_hash

    return {
        "status": "valid",
        "events_checked": len(ledger)
    }

def events_by_source(source):

    ledger = load_ledger()

    return [
        e for e in ledger
        if e.get("source") == source
    ]
