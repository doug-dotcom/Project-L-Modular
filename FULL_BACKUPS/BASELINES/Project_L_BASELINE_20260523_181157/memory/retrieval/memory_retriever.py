import json
from pathlib import Path

ROOT = Path("C:/Shine_L")

# =========================================================
# MEMORY FILES
# =========================================================

memory_files = {
    "identity": ROOT / "memory" / "domains" / "identity.json",
    "family": ROOT / "memory" / "domains" / "family.json",
    "work": ROOT / "memory" / "domains" / "work.json",
    "sport": ROOT / "memory" / "domains" / "sport.json",
    "health": ROOT / "memory" / "domains" / "health.json",
    "general": ROOT / "memory" / "domains" / "general.json",
    "emotional": ROOT / "memory" / "emotional" / "emotional_state.json",
    "learning": ROOT / "memory" / "learning" / "adaptive_learning.json",
    "patterns": ROOT / "memory" / "patterns" / "memory_patterns.json"
}

# =========================================================
# LOAD STORE
# =========================================================

def load_store(path):
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(raw, dict):
            return raw.get("memories", [])

        if isinstance(raw, list):
            return raw

    except:
        return []

    return []

# =========================================================
# SEARCH FUNCTION
# =========================================================

def search_memories(query):

    query = query.lower()

    results = []

    for category, path in memory_files.items():

        memories = load_store(path)

        for memory in memories:

            content = str(memory.get("content", "")).lower()

            score = 0

            # -------------------------------------------------
            # SIMPLE KEYWORD MATCHING
            # -------------------------------------------------

            for word in query.split():

                if word in content:
                    score += 1

            if score > 0:

                results.append({
                    "category": category,
                    "score": score,
                    "memory": memory
                })

    # =====================================================
    # SORT BY SCORE
    # =====================================================

    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:15]

# =========================================================
# INTERACTIVE TEST
# =========================================================

print("")
print("==========================================")
print(" SHINE L MEMORY RETRIEVAL ENGINE ")
print("==========================================")
print("")

while True:

    query = input("Ask L something (or type exit): ")

    if query.lower() == "exit":
        break

    results = search_memories(query)

    print("")
    print("==========================================")
    print(f" RESULTS FOR: {query}")
    print("==========================================")

    if not results:
        print("No matching memories found.")
        print("")
        continue

    for i, result in enumerate(results, 1):

        category = result["category"]
        score = result["score"]
        content = result["memory"].get("content", "")

        print("")
        print(f"[{i}] CATEGORY: {category}")
        print(f"SCORE: {score}")
        print(f"MEMORY: {content}")

    print("")
