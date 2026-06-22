# =====================================================
# PROJECT L — WILLY V1
# Wisdom Agent
# =====================================================
# V1 PERIMETER:
# - Manual lesson input only
# - No retrieval
# - No automation
# - No batch processing
# - No Ricki integration
#
# JOB:
# Lesson -> Principle -> Wisdom Warehouse
# =====================================================

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")
from datetime import datetime
from typing import Optional, Dict, Any

from supabase import create_client


class Willy:
    """
    Willy V1 converts manually supplied lessons into wisdom principles
    and saves approved principles into Supabase wisdom_warehouse.
    """

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        )

        if not self.supabase_url or not self.supabase_key:
            raise RuntimeError(
                "Missing Supabase environment variables: SUPABASE_URL and SUPABASE key"
            )

        self.supabase = create_client(self.supabase_url, self.supabase_key)

    # -------------------------------------------------
    # REVIEW LESSON
    # -------------------------------------------------
    def review_lesson(
        self,
        lesson: str,
        category: Optional[str] = None,
        confidence: int = 85,
        approved_by: str = "Doug",
    ) -> Dict[str, Any]:
        """
        Manual V1 review.

        Doug supplies the lesson.
        Willy forms a principle candidate.
        Doug decides whether to save it.
        """

        if not lesson or not lesson.strip():
            raise ValueError("Lesson cannot be empty.")

        principle = self._extract_principle(lesson)

        return {
            "agent": "Willy",
            "version": "v1",
            "lesson": lesson.strip(),
            "principle": principle,
            "category": category or self._suggest_category(lesson),
            "confidence": confidence,
            "approved_by": approved_by,
            "recommendation": "Review principle. If Doug approves, save to wisdom_warehouse.",
            "created_at": datetime.utcnow().isoformat(),
        }

    # -------------------------------------------------
    # SAVE PRINCIPLE
    # -------------------------------------------------
    def save_principle(
        self,
        principle: str,
        category: Optional[str] = None,
        confidence: int = 85,
        approved_by: str = "Doug",
    ) -> Dict[str, Any]:
        """
        Saves an approved principle into wisdom_warehouse.
        """

        if not principle or not principle.strip():
            raise ValueError("Principle cannot be empty.")

        row = {
            "principle": principle.strip(),
            "category": category,
            "confidence": confidence,
            "lesson_used": 0,
            "version": 1,
            "approved_by": approved_by,
        }

        result = (
            self.supabase
            .table("wisdom_warehouse")
            .insert(row)
            .execute()
        )

        return {
            "saved": True,
            "table": "wisdom_warehouse",
            "principle": principle.strip(),
            "category": category,
            "confidence": confidence,
            "approved_by": approved_by,
            "result": result.data,
        }

    # -------------------------------------------------
    # USAGE COUNTER
    # -------------------------------------------------
    def increment_lesson_used(self, wisdom_id: str) -> Dict[str, Any]:
        """
        Increments lesson_used when a wisdom principle is actually used.
        """

        existing = (
            self.supabase
            .table("wisdom_warehouse")
            .select("lesson_used")
            .eq("id", wisdom_id)
            .single()
            .execute()
        )

        current = existing.data.get("lesson_used", 0)
        new_value = current + 1

        result = (
            self.supabase
            .table("wisdom_warehouse")
            .update({"lesson_used": new_value})
            .eq("id", wisdom_id)
            .execute()
        )

        return {
            "updated": True,
            "wisdom_id": wisdom_id,
            "lesson_used": new_value,
            "result": result.data,
        }

    # -------------------------------------------------
    # WAREHOUSE COUNT
    # -------------------------------------------------
    def count_principles(self) -> Dict[str, Any]:
        """
        Counts current wisdom principles.
        V2 unlock condition is 50 approved principles.
        """

        result = (
            self.supabase
            .table("wisdom_warehouse")
            .select("id", count="exact")
            .execute()
        )

        count = result.count or 0

        return {
            "wisdom_count": count,
            "v1_target": 50,
            "v2_unlocked": count >= 50,
            "remaining_to_v2": max(0, 50 - count),
        }

    # -------------------------------------------------
    # INTERNAL PRINCIPLE EXTRACTION
    # -------------------------------------------------
    def _extract_principle(self, lesson: str) -> str:
        """
        V1 simple principle formation.

        This is intentionally conservative.
        L can improve the wording before saving.
        """

        text = lesson.strip()

        lower = text.lower()

        if "aods" in lower:
            return "Canonical definitions prevent architectural drift."

        if "clarity" in lower or "visible" in lower or "visibility" in lower:
            return "Visibility creates clarity, and clarity improves trust."

        if "shortcut" in lower or "cheat" in lower or "pattern" in lower:
            return "Start from the closest proven pattern, then refine for the new problem."

        if "recovery" in lower or "alcohol" in lower or "drink" in lower:
            return "Short-term relief can create long-term suffering."

        if "connection" in lower:
            return "Connection weakens unhealthy thinking and strengthens recovery."

        return f"Extract the reusable principle from this lesson: {text}"

    # -------------------------------------------------
    # INTERNAL CATEGORY SUGGESTION
    # -------------------------------------------------
    def _suggest_category(self, lesson: str) -> str:
        lower = lesson.lower()

        if "aods" in lower or "architecture" in lower or "sql" in lower:
            return "Architecture"

        if "clarity" in lower or "visibility" in lower:
            return "Clarity"

        if "recovery" in lower or "alcohol" in lower or "drink" in lower:
            return "Recovery"

        if "connection" in lower or "friend" in lower or "family" in lower:
            return "Relationships"

        if "pattern" in lower or "shortcut" in lower or "cheat" in lower:
            return "Problem Solving"

        return "General"


# =====================================================
# SIMPLE MANUAL TEST
# =====================================================
if __name__ == "__main__":
    willy = Willy()

    lesson = "AODS means Atomic One Drop Script, not a plan or roadmap."

    review = willy.review_lesson(lesson)
    print("WILLY REVIEW")
    print(review)

    print("WAREHOUSE COUNT")
    print(willy.count_principles())

