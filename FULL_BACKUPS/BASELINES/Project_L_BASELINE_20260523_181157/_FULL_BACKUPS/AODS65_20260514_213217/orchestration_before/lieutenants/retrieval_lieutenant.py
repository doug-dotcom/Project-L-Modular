# ============================================================
# RETRIEVAL LIEUTENANT
# Phase 15 - Lieutenant Systems
# ============================================================

from typing import List, Dict


class RetrievalLieutenant:

    def __init__(self):

        self.name = "Retrieval Lieutenant"

        self.status = "active"

        self.version = "AODS61"

    # ========================================================
    # SCORE MEMORY RESULTS
    # ========================================================

    def rank_results(
        self,
        results: List[Dict]
    ) -> List[Dict]:

        ranked = []

        for result in results:

            score = result.get(
                "_score",
                0
            )

            entry = result.get(
                "entry",
                {}
            )

            bonus = 0

            # =================================================
            # RECENCY BONUS
            # =================================================

            if isinstance(entry, dict):

                if entry.get("important"):
                    bonus += 3

                if entry.get("pinned"):
                    bonus += 5

                if entry.get("type") == "identity":
                    bonus += 4

                if entry.get("type") == "relationship":
                    bonus += 2

            final_score = score + bonus

            result["_retrieval_rank"] = final_score

            ranked.append(result)

        ranked.sort(
            key=lambda x: x.get(
                "_retrieval_rank",
                0
            ),
            reverse=True
        )

        return ranked

    # ========================================================
    # FILTER LOW VALUE RESULTS
    # ========================================================

    def filter_noise(
        self,
        results: List[Dict],
        threshold: int = 1
    ) -> List[Dict]:

        filtered = []

        for result in results:

            rank = result.get(
                "_retrieval_rank",
                result.get("_score", 0)
            )

            if rank >= threshold:

                filtered.append(result)

        return filtered

    # ========================================================
    # FINAL PROCESS
    # ========================================================

    def process_retrieval(
        self,
        results: List[Dict]
    ) -> List[Dict]:

        ranked = self.rank_results(results)

        filtered = self.filter_noise(ranked)

        return filtered

    # ========================================================
    # STATUS
    # ========================================================

    def runtime_status(self):

        return {
            "name": self.name,
            "status": self.status,
            "version": self.version
        }


# ============================================================
# SINGLETON
# ============================================================

RETRIEVAL_LIEUTENANT = (
    RetrievalLieutenant()
)
