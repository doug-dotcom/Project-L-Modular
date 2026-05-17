# ============================================================
# CONTINUITY LIEUTENANT
# Phase 15 - Lieutenant Systems
# ============================================================

from pathlib import Path
import json
from datetime import datetime


ROOT = Path(r"C:\Shine_L")

CONTINUITY_FILE = (
    ROOT
    / "memory"
    / "continuity"
    / "continuity_state.json"
)


class ContinuityLieutenant:

    def __init__(self):

        self.name = "Continuity Lieutenant"

        self.status = "active"

        self.version = "AODS65"

    # ========================================================
    # JSON HELPERS
    # ========================================================

    def load_state(self):

        try:

            if not CONTINUITY_FILE.exists():
                return {}

            return json.loads(
                CONTINUITY_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as e:

            print(
                "CONTINUITY LOAD ERROR:",
                e
            )

            return {}

    def save_state(
        self,
        data
    ):

        try:

            CONTINUITY_FILE.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            CONTINUITY_FILE.write_text(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

        except Exception as e:

            print(
                "CONTINUITY SAVE ERROR:",
                e
            )

    # ========================================================
    # UPDATE CONTEXT
    # ========================================================

    def update_context(
        self,
        user_msg: str,
        deployment: dict = None
    ):

        state = self.load_state()

        state["last_message"] = user_msg

        state["updated_at"] = (
            datetime.now().isoformat()
        )

        if deployment:

            state["last_captain"] = (
                deployment.get("captain")
            )

        topics = self.extract_topics(
            user_msg
        )

        state["topics"] = topics

        self.save_state(state)

        return state

    # ========================================================
    # SIMPLE TOPIC EXTRACTION
    # ========================================================

    def extract_topics(
        self,
        user_msg: str
    ):

        text = user_msg.lower()

        keywords = [

            "memory",
            "email",
            "calendar",
            "finance",
            "research",
            "image",
            "task",
            "architecture",
            "runtime",
            "deployment",
            "kids",
            "recovery",
            "hockey",
            "shine"
        ]

        topics = []

        for keyword in keywords:

            if keyword in text:
                topics.append(keyword)

        return topics

    # ========================================================
    # BUILD CONTINUITY LAYER
    # ========================================================

    def build_continuity_layer(self):

        state = self.load_state()

        if not state:
            return ""

        topics = state.get(
            "topics",
            []
        )

        captain = state.get(
            "last_captain",
            None
        )

        updated = state.get(
            "updated_at",
            None
        )

        return f"""

CONTINUITY LAYER:
- Last captain: {captain}
- Active topics: {topics}
- Last update: {updated}

Maintain conversational continuity where appropriate.
Avoid abrupt context drift.

"""

    # ========================================================
    # STATUS
    # ========================================================

    def runtime_status(self):

        return {
            "name": self.name,
            "status": self.status,
            "version": self.version
        }


CONTINUITY_LIEUTENANT = (
    ContinuityLieutenant()
)
