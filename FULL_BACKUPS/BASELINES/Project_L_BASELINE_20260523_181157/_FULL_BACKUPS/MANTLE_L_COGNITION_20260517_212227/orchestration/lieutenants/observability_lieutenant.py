# ============================================================
# OBSERVABILITY LIEUTENANT
# Phase 15 - Lieutenant Systems
# ============================================================

from pathlib import Path
import json
from datetime import datetime


ROOT = Path(r"C:\Shine_L")

EVENTS_FILE = (
    ROOT
    / "memory"
    / "observability"
    / "runtime_events.json"
)


class ObservabilityLieutenant:

    def __init__(self):

        self.name = "Observability Lieutenant"

        self.status = "active"

        self.version = "AODS66"

    # ========================================================
    # JSON HELPERS
    # ========================================================

    def load_events(self):

        try:

            if not EVENTS_FILE.exists():
                return []

            return json.loads(
                EVENTS_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as e:

            print(
                "OBSERVABILITY LOAD ERROR:",
                e
            )

            return []

    def save_events(
        self,
        data
    ):

        try:

            EVENTS_FILE.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            EVENTS_FILE.write_text(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

        except Exception as e:

            print(
                "OBSERVABILITY SAVE ERROR:",
                e
            )

    # ========================================================
    # RECORD EVENT
    # ========================================================

    def record_event(
        self,
        event_type: str,
        payload: dict
    ):

        events = self.load_events()

        events.append({

            "timestamp": (
                datetime.now().isoformat()
            ),

            "event_type": event_type,

            "payload": payload
        })

        # Keep last 500 events only
        events = events[-500:]

        self.save_events(events)

        return {
            "recorded": True,
            "event_type": event_type
        }

    # ========================================================
    # RUNTIME SNAPSHOT
    # ========================================================

    def build_runtime_snapshot(self):

        events = self.load_events()

        latest = events[-10:]

        captain_counts = {}

        for item in events:

            payload = item.get(
                "payload",
                {}
            )

            captain = payload.get(
                "captain"
            )

            if captain:

                captain_counts[
                    captain
                ] = (
                    captain_counts.get(
                        captain,
                        0
                    ) + 1
                )

        return {
            "total_events": len(events),
            "latest_events": latest,
            "captain_counts": captain_counts
        }

    # ========================================================
    # STATUS
    # ========================================================

    def runtime_status(self):

        snapshot = (
            self.build_runtime_snapshot()
        )

        return {
            "name": self.name,
            "status": self.status,
            "version": self.version,
            "events": snapshot[
                "total_events"
            ]
        }


OBSERVABILITY_LIEUTENANT = (
    ObservabilityLieutenant()
)
