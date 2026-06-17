# =====================================================
# PATTERN EXTRACTOR
# TIER 1 - AODS 1
# =====================================================

from collections import Counter
from typing import Any, Dict, List


def extract_patterns(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract repeating themes, lessons, entities, and relationship types
    from research memory records.
    """

    theme_counter = Counter()
    lesson_counter = Counter()
    entity_counter = Counter()
    relationship_counter = Counter()

    for record in records or []:

        for item in record.get("themes", []) or []:
            theme_counter[str(item).strip().lower()] += 1

        for item in record.get("lessons", []) or []:
            lesson_counter[str(item).strip()] += 1

        for item in record.get("entities", []) or []:
            if isinstance(item, dict):
                name = item.get("name")
            else:
                name = item

            if name:
                entity_counter[str(name).strip()] += 1

        for item in record.get("relationships", []) or []:
            if isinstance(item, dict):
                rel = item.get("relationship")
            else:
                rel = item

            if rel:
                relationship_counter[str(rel).strip().lower()] += 1

    return {
        "agent": "Pattern Extractor",
        "status": "ok",
        "record_count": len(records or []),
        "patterns": {
            "themes": dict(theme_counter.most_common()),
            "lessons": dict(lesson_counter.most_common()),
            "entities": dict(entity_counter.most_common()),
            "relationships": dict(relationship_counter.most_common()),
        },
    }


if __name__ == "__main__":
    sample = [
        {
            "themes": ["memory", "research", "memory"],
            "lessons": ["Store before recall"],
            "entities": [{"name": "Project L"}, {"name": "Mary"}],
            "relationships": [{"relationship": "supports"}],
        }
    ]

    result = extract_patterns(sample)

    print(result)

    assert result["status"] == "ok"
    assert result["patterns"]["themes"]["memory"] == 2
