# =====================================================
# AODS 11.2
# BATCH COACH PROCESSING
# Memory -> Coach -> LLGR
# =====================================================

import sys
import json

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.coach.mary_coach_adapter import run_memory_to_coach


def run_batch_memories(memories):

    results = []

    print("=====================================================")
    print("AODS 11.2 - BATCH COACH PROCESSING")
    print("=====================================================")

    for index, memory in enumerate(memories, start=1):

        print(f"Processing memory {index}...")

        try:
            result = run_memory_to_coach(memory)

            results.append({
                "memory_number": index,
                "status": "processed",
                "content": memory.get("content", ""),
                "result": result
            })

            print(f"Memory {index} processed.")

        except Exception as e:
            results.append({
                "memory_number": index,
                "status": "error",
                "content": memory.get("content", ""),
                "error": str(e)
            })

            print(f"Memory {index} ERROR: {e}")

    print("=====================================================")
    print(f"AODS 11.2 COMPLETE - {len(results)} memories attempted")
    print("=====================================================")

    return results


if __name__ == "__main__":

    memories = [
        {
            "content": "Doug noticed he kept seeking validation from Pauline.",
            "subjects": ["Pauline"],
            "values": ["Growth", "Truth"],
            "patterns": ["Validation Seeking"],
            "relationships": [],
            "importance": 80,
            "salience": 90,
            "anchor": True
        },
        {
            "content": "Doug realised he keeps handing the keys to mentors.",
            "subjects": ["Sean Graham", "Walshy", "Dad"],
            "values": ["Agency", "Growth"],
            "patterns": ["Authority Transfer"],
            "relationships": [],
            "importance": 95,
            "salience": 95,
            "anchor": True
        },
        {
            "content": "Doug recognised the difference between memory in and memory out.",
            "subjects": ["Project L", "Mary", "Sally", "Carol"],
            "values": ["Learning", "Truth"],
            "patterns": ["Cognitive Insight"],
            "relationships": [],
            "importance": 90,
            "salience": 85,
            "anchor": True
        }
    ]

    results = run_batch_memories(memories)

    print(json.dumps(results, indent=2))

