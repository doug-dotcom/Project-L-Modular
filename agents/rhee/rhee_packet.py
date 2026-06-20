from supabase import create_client
from dotenv import load_dotenv

import os

from rhee import (
    calculate_memory_score,
    load_all_memories
)

# =====================================================
# ENV
# =====================================================

load_dotenv()

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY"
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# =====================================================
# BUILD RECALL PACKET
# =====================================================

def build_recall_packet(subject):

    memories = load_all_memories()

    packet = []

    for memory in memories:

        score = calculate_memory_score(
            memory,
            subject
        )

        if score <= 0:
            continue

        memory["_score"] = score

        packet.append(memory)

    packet.sort(
        key=lambda x: x["_score"],
        reverse=True
    )

    return packet

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    packet = build_recall_packet(
        "Luella"
    )

    print()
    print("=" * 50)
    print("RHEE RECALL PACKET")
    print("=" * 50)
    print()

    print(
        f"MEMORIES FOUND: {len(packet)}"
    )

    print()

    for memory in packet[:10]:

        print(
            f"{memory['_score']} | "
            f"{memory.get('_table')} | "
            f"{memory.get('primary_subject')}"
        )

        print(
            memory.get(
                "content",
                ""
            )[:150]
        )

        print()

