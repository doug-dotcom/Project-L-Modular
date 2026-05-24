import json

from core.json_store import (
    safe_load_json,
    safe_save_json,
)

from core.paths import (
    LIFE_STORY_FILE,
    PROFILE_FILE,
)

from memory.memory_audit import (
    audit_memory_event,
)


MEMORY_IMPORTANCE = {
    "kids": 10,
    "children": 10,
    "iyla": 10,
    "ashton": 10,
    "luella": 10,
    "mehlia": 10,
    "army": 9,
    "east timor": 10,
    "kapooka": 9,
    "deployment": 9,
    "recovery": 10,
    "na": 10,
    "aa": 10,
    "stepwork": 9,
    "shine": 10,
    "purpose": 9,
    "identity": 8,
    "trauma": 9,
    "family": 10,
    "clarity": 8,
}


SEMANTIC_LINKS = {

    "east timor": [
        "army",
        "kapooka",
        "transport",
        "military",
        "enlistment",
        "deployment",
        "reserve scheme",
        "timor",
    ],

    "army": [
        "kapooka",
        "east timor",
        "transport corps",
        "deployment",
        "reserve scheme",
        "military",
    ],

    "school": [
        "girls",
        "childhood",
        "grade",
        "growing up",
        "teenage",
        "adolescence",
    ],

    "recovery": [
        "na",
        "aa",
        "meetings",
        "addiction",
        "stepwork",
        "sobriety",
        "clean",
    ],

    "family": [
        "kids",
        "children",
        "mehlia",
        "luella",
        "iyla",
        "ashton",
    ],
}


def load_profile():

    return safe_load_json(
        PROFILE_FILE,
        {}
    )


def calculate_memory_score(text):

    score = 0

    text_lower = text.lower()

    for key, value in MEMORY_IMPORTANCE.items():

        if key in text_lower:

            score += value

    return score


def detect_intent(user_text):

    text = user_text.lower()

    if (
        "full file" in text
        or "full document" in text
        or "read full" in text
        or "show full" in text
        or "word for word" in text
        or "read the full" in text
        or "full story" in text
    ):
        return "full_recall"

    if (
        "remember" in text
        or "recall" in text
        or "what do you know" in text
        or "tell me about" in text
        or "what matters" in text
    ):
        return "memory_recall"

    return "normal"


def expand_search_terms(query):

    query_lower = query.lower()

    terms = [query_lower]

    words = query_lower.replace("?", "").replace(".", "").split()

    terms.extend(words)

    for key, linked_terms in SEMANTIC_LINKS.items():

        if key in query_lower:

            terms.extend(linked_terms)

    return list(
        set(
            [
                t.strip()
                for t in terms
                if t.strip()
            ]
        )
    )


def search_life_story(query):

    stories = safe_load_json(
        LIFE_STORY_FILE,
        []
    )

    if not isinstance(stories, list):

        return []

    search_terms = expand_search_terms(query)

    matches = []

    for item in stories:

        title = str(item.get("title", ""))

        preview = str(item.get("preview", ""))

        full_content = str(
            item.get(
                "full_content",
                item.get("content", "")
            )
        )

        text_blob = (
            f"{title} {preview} {full_content}"
        ).lower()

        score = 0

        for term in search_terms:

            if term in text_blob:

                score += 1

        score += int(
            item.get("score", 0)
        )

        if score > 0:

            copy_item = dict(item)

            copy_item["_score"] = score

            matches.append(copy_item)

    matches.sort(
        key=lambda x: x.get("_score", 0),
        reverse=True
    )

    return matches[:5]


def save_to_life_story(
    title,
    content_text
):

    stories = safe_load_json(
        LIFE_STORY_FILE,
        []
    )

    if not isinstance(stories, list):

        stories = []

    preview_text = content_text[:3000]

    memory_score = calculate_memory_score(
        content_text
    )

    entry = {
        "title": title,
        "preview": preview_text,
        "full_content": content_text,
        "score": memory_score,
    }

    stories.append(entry)

    safe_save_json(
        LIFE_STORY_FILE,
        stories
    )

    audit_memory_event(
        "save",
        LIFE_STORY_FILE,
        {
            "title": title,
            "characters": len(content_text),
            "score": memory_score
        }
    )


def build_profile_context():

    profile = load_profile()

    if not profile:

        return ""

    return (
        "\n\nCANONICAL PROFILE MEMORY:\n"
        + json.dumps(
            profile,
            indent=2,
            ensure_ascii=False,
        )
    )


def build_story_context(user_msg):

    matches = search_life_story(
        user_msg
    )

    if not matches:

        return ""

    story_context = "\n\nRELEVANT STORY MEMORY:\n"

    for item in matches:

        story_context += "\n--- STORY MEMORY ---\n"

        story_context += item.get(
            "preview",
            ""
        )

    return story_context
