import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path("C:/Shine_L")
load_dotenv(ROOT / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY missing in C:/Shine_L/.env")
    raise SystemExit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILES = {
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

def load_memories(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("memories", [])
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []

def text_of(memory):
    content = memory.get("content", "")
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return str(content)

def search_memories(query, limit=30):
    q_words = [w.lower() for w in query.split() if len(w) > 2]
    results = []

    for category, path in MEMORY_FILES.items():
        memories = load_memories(path)

        for memory in memories:
            text = text_of(memory)
            low = text.lower()

            score = 0

            for word in q_words:
                if word in low:
                    score += 1

            # gentle category boosts
            if "kid" in query.lower() or "children" in query.lower() or "family" in query.lower():
                if category == "family":
                    score += 3

            if "hockey" in query.lower() or "sport" in query.lower():
                if category == "sport":
                    score += 3

            if "work" in query.lower() or "anz" in query.lower() or "financial" in query.lower():
                if category == "work":
                    score += 3

            if "feel" in query.lower() or "emotion" in query.lower() or "recovery" in query.lower():
                if category in ["emotional", "patterns", "learning"]:
                    score += 2

            if "values" in query.lower() or "who am i" in query.lower() or "about me" in query.lower():
                if category in ["identity", "general", "learning"]:
                    score += 2

            if score > 0:
                results.append({
                    "category": category,
                    "score": score,
                    "created_at": memory.get("created_at", ""),
                    "content": text
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def build_context(results):
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. Category: {r['category']} | Score: {r['score']} | Date: {r['created_at']}\nMemory: {r['content']}"
        )
    return "\n\n".join(lines)

def ask_llm(query, memories):
    memory_context = build_context(memories)

    system_prompt = """
You are L, a memory-aware AI companion for Doug.
Use ONLY the provided memory context when making personal claims.
Be warm, clear, grounded, and concise.
If memory is incomplete, say so honestly.
Do not pretend to know things that are not in the retrieved memories.
Summarize patterns when the memories support them.
"""

    user_prompt = f"""
Doug asked:
{query}

Retrieved memory context:
{memory_context}

Answer Doug using the retrieved memories.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

print("")
print("==========================================")
print(" SHINE L STAGE 4 - LLM MEMORY RECALL ")
print("==========================================")
print("")

while True:
    query = input("Ask L with memory (or type exit): ")

    if query.lower().strip() == "exit":
        break

    results = search_memories(query)

    if not results:
        print("")
        print("No matching memories found.")
        print("")
        continue

    print("")
    print(f"Retrieved {len(results)} memories. Asking L...")
    print("")

    answer = ask_llm(query, results)

    print("==========================================")
    print(" L MEMORY RESPONSE ")
    print("==========================================")
    print(answer)
    print("==========================================")
    print("")
