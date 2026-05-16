# ============================================================
# CONFIDENCE LIEUTENANT
# Phase 15 - Lieutenant Systems
# ============================================================

from typing import List, Dict, Any


class ConfidenceLieutenant:

    def __init__(self):

        self.name = "Confidence Lieutenant"
        self.status = "active"
        self.version = "AODS62"

    # ========================================================
    # ASSESS MEMORY CONFIDENCE
    # ========================================================

    def assess_memory_confidence(
        self,
        matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        if not matches:

            return {
                "confidence": "low",
                "score": 0,
                "reason": "no_memory_matches",
                "instruction": "be transparent about uncertainty"
            }

        top_score = 0
        total_score = 0
        high_value_hits = 0

        for item in matches:

            score = (
                item.get("_retrieval_rank")
                or item.get("_score")
                or 0
            )

            total_score += score

            if score > top_score:
                top_score = score

            entry = item.get("entry", {})

            if isinstance(entry, dict):

                if entry.get("important"):
                    high_value_hits += 1

                if entry.get("pinned"):
                    high_value_hits += 1

                if entry.get("type") in [
                    "identity",
                    "relationship",
                    "project",
                    "memory"
                ]:
                    high_value_hits += 1

        average_score = total_score / max(len(matches), 1)

        if top_score >= 10 or high_value_hits >= 3:
            confidence = "high"

        elif top_score >= 5 or average_score >= 3:
            confidence = "medium"

        else:
            confidence = "low"

        return {
            "confidence": confidence,
            "score": top_score,
            "average_score": average_score,
            "match_count": len(matches),
            "high_value_hits": high_value_hits,
            "reason": "retrieval_quality_assessment",
            "instruction": self.instruction_for(confidence)
        }

    # ========================================================
    # INSTRUCTION LAYER
    # ========================================================

    def instruction_for(
        self,
        confidence: str
    ) -> str:

        if confidence == "high":

            return (
                "Use retrieved memory confidently, but do not exaggerate."
            )

        if confidence == "medium":

            return (
                "Use memory carefully. Distinguish known memory from inference."
            )

        return (
            "Memory confidence is weak. Avoid guessing. Ask or state uncertainty."
        )

    # ========================================================
    # BUILD PROMPT LAYER
    # ========================================================

    def build_confidence_prompt_layer(
        self,
        confidence_data: Dict[str, Any]
    ) -> str:

        confidence = confidence_data.get(
            "confidence",
            "low"
        )

        instruction = confidence_data.get(
            "instruction",
            self.instruction_for(confidence)
        )

        return f"""

MEMORY CONFIDENCE LAYER:
- Confidence: {confidence}
- Score: {confidence_data.get("score", 0)}
- Match count: {confidence_data.get("match_count", 0)}
- Instruction: {instruction}

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


CONFIDENCE_LIEUTENANT = ConfidenceLieutenant()
