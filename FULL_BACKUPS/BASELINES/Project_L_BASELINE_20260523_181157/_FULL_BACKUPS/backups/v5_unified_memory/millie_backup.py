import os
import json
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

MEMORY_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "millie_memories.json"
)

os.makedirs(
    os.path.dirname(MEMORY_FILE),
    exist_ok=True
)


def _load():

    try:

        if not os.path.exists(MEMORY_FILE):

            return []

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("MILLIE LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("MILLIE SAVE ERROR:", e)


def should_handle(message: str) -> bool:

    text = message.lower()

    direct_words = [
        "millie",
        "memory keeper",
        "save this memory",
        "remember this",
        "preserve this",
        "story memory",
        "memory timeline",
        "life story",
        "legacy memory",
        "add this to my memory",
        "save this to memory"
    ]

    return any(
        phrase in text
        for phrase in direct_words
    )


def _clean_memory_text(message: str) -> str:

    text = message.strip()

    remove_phrases = [
        "millie",
        "memory keeper",
        "save this memory",
        "remember this",
        "preserve this",
        "add this to my memory",
        "save this to memory"
    ]

    for phrase in remove_phrases:

        text = text.replace(phrase, "")
        text = text.replace(phrase.title(), "")

    return text.strip()


def add_memory(message: str):

    memories = _load()

    clean = _clean_memory_text(message)

    if not clean:

        clean = message.strip()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": "memory",
        "source": "Millie",
        "content": clean,
        "tags": _detect_tags(clean)
    }

    memories.append(entry)

    _save(memories)

    return entry


def _detect_tags(text: str):

    lower = text.lower()

    tags = []

    tag_map = {
        "kids": ["kids", "children", "iyla", "ashton", "luella", "mehlia"],
        "legacy": ["legacy", "book", "story", "grandchildren", "family history"],
        "shine": ["shine", "l", "agent", "ecosystem"],
        "emotion": ["feel", "felt", "emotion", "fear", "happy", "sad", "overwhelm"],
        "recovery": ["na", "aa", "recovery", "sober", "clean"],
        "health": ["dementia", "memory loss", "cognitive", "health"]
    }

    for tag, words in tag_map.items():

        if any(word in lower for word in words):

            tags.append(tag)

    return tags


def search_memories(message: str):

    memories = _load()

    text = message.lower()

    results = []

    for item in memories:

        content = item.get("content", "").lower()

        score = 0

        for word in text.split():

            if len(word) > 3 and word in content:

                score += 1

        if score > 0:

            copy = dict(item)
            copy["_score"] = score
            results.append(copy)

    results.sort(
        key=lambda x: x.get("_score", 0),
        reverse=True
    )

    return results[:5]


def handle_memory_request(message: str):

    text = message.lower()

    if (
        "recall" in text
        or "find" in text
        or "search" in text
        or "what do you remember" in text
    ):

        results = search_memories(message)

        if not results:

            return (
                "# 🧠 Millie Memory Keeper\n\n"
                "I could not find a matching Millie memory yet."
            )

        reply = "# 🧠 Millie Memory Keeper\n\n"
        reply += "Here are the strongest matching memories:\n\n"

        for i, item in enumerate(results, start=1):

            reply += f"## Memory {i}\n"
            reply += item.get("content", "") + "\n\n"

            tags = item.get("tags", [])

            if tags:

                reply += "Tags: " + ", ".join(tags) + "\n\n"

        return reply

    entry = add_memory(message)

    return (
        "# 🧠 Millie Memory Keeper\n\n"
        "Memory saved successfully.\n\n"
        "Saved memory:\n\n"
        + entry.get("content", "")
        + "\n\nTags: "
        + ", ".join(entry.get("tags", []))
    )
