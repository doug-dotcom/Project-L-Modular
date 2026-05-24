# ============================================================
# SUPPRESSION LIEUTENANT
# Phase 15 - Lieutenant Systems
# ============================================================

from typing import Dict, Any


class SuppressionLieutenant:

    def __init__(self):

        self.name = "Suppression Lieutenant"

        self.status = "active"

        self.version = "AODS64"

        self.meta_terms = [

            "architecture",
            "server.py",
            "backend",
            "frontend",
            "runtime",
            "captain",
            "lieutenant",
            "orchestration",
            "deployment",
            "system design",
            "api",
            "platform"
        ]

        self.low_priority = [

            "😂",
            "lol",
            "haha",
            ".",
            "ok",
            "nice",
            "cool"
        ]

    # ========================================================
    # DETECT META DISCUSSION
    # ========================================================

    def detect_meta(
        self,
        user_msg: str
    ) -> bool:

        text = user_msg.lower()

        for term in self.meta_terms:

            if term in text:
                return True

        return False

    # ========================================================
    # DETECT LOW PRIORITY
    # ========================================================

    def detect_low_priority(
        self,
        user_msg: str
    ) -> bool:

        text = user_msg.lower().strip()

        if len(text) <= 2:
            return True

        for item in self.low_priority:

            if text == item:
                return True

        return False

    # ========================================================
    # SHOULD SUPPRESS
    # ========================================================

    def should_suppress(
        self,
        user_msg: str
    ) -> Dict[str, Any]:

        meta = self.detect_meta(
            user_msg
        )

        low = self.detect_low_priority(
            user_msg
        )

        suppress = False
        reason = None

        if meta:

            suppress = True
            reason = "meta_discussion"

        elif low:

            suppress = True
            reason = "low_priority"

        return {
            "suppress": suppress,
            "reason": reason,
            "meta": meta,
            "low_priority": low
        }

    # ========================================================
    # STATUS
    # ========================================================

    def runtime_status(self):

        return {
            "name": self.name,
            "status": self.status,
            "version": self.version
        }


SUPPRESSION_LIEUTENANT = (
    SuppressionLieutenant()
)
