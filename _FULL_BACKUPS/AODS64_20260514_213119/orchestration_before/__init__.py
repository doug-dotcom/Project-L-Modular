# ============================================================
# ROUTING LIEUTENANT
# Phase 15 - Lieutenant Systems
# ============================================================

from typing import List, Dict, Any


class RoutingLieutenant:

    def __init__(self):

        self.name = "Routing Lieutenant"

        self.status = "active"

        self.version = "AODS63"

    # ========================================================
    # SCORE CAPTAIN
    # ========================================================

    def score_captain(
        self,
        captain,
        user_msg: str
    ) -> Dict[str, Any]:

        score = 0

        try:

            should_handle = captain.should_handle(
                user_msg
            )

            if should_handle:
                score += 10

        except Exception as e:

            return {
                "captain": captain.name,
                "score": -1,
                "error": str(e)
            }

        text = user_msg.lower()

        domain = str(
            getattr(captain, "domain", "")
        ).lower()

        # ====================================================
        # DOMAIN WEIGHTING
        # ====================================================

        if domain in text:
            score += 5

        if "urgent" in text:
            score += 1

        if "important" in text:
            score += 1

        return {
            "captain": captain,
            "captain_name": captain.name,
            "score": score,
            "should_handle": should_handle
        }

    # ========================================================
    # SELECT BEST CAPTAIN
    # ========================================================

    def select_best_captain(
        self,
        captains: List[Any],
        user_msg: str
    ) -> Dict[str, Any]:

        scored = []

        for captain in captains:

            result = self.score_captain(
                captain,
                user_msg
            )

            scored.append(result)

        scored.sort(
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        best = scored[0] if scored else None

        return {
            "best": best,
            "all_scores": scored
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


ROUTING_LIEUTENANT = RoutingLieutenant()

