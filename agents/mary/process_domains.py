import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOMAIN_DIR = ROOT / "memory" / "domains"

DOMAIN_VALUES = {

    "family": [
        "Love",
        "Protection",
        "Connection",
        "Self Respect"
    ],

    "recovery": [
        "Truth",
        "Growth",
        "Service",
        "Connection"
    ],

    "sport": [
        "Connection",
        "Commitment",
        "Discipline",
        "Achievement",
        "Belonging"
    ],

    "project_l": [
        "Service",
        "Teaching",
        "Understanding",
        "Growth"
    ],

    "work": [
        "Achievement",
        "Contribution",
        "Integrity",
        "Growth"
    ],

    "identity": [
        "Self Knowledge",
        "Truth",
        "Growth",
        "Identity"
    ],

    "health": [
        "Wellbeing",
        "Longevity",
        "Energy",
        "Freedom"
    ],

    "relationships": [
        "Connection",
        "Love",
        "Trust",
        "Belonging"
    ],

    "knowledge": [
        "Learning",
        "Discovery",
        "Understanding",
        "Growth"
    ],

    "finance": [
        "Security",
        "Freedom",
        "Peace",
        "Responsibility"
    ],

    "general": [
        "Growth",
        "Connection",
        "Learning"
    ]

}

FILES_PROCESSED = 0
MEMORIES_PROCESSED = 0
VALUES_ASSIGNED = 0

for file in DOMAIN_DIR.glob("*.json"):

    try:

        with open(
            file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(
            data,
            list
        ):
            continue

        domain_name = file.stem

        domain_values = DOMAIN_VALUES.get(
            domain_name,
            []
        )

        changed = False

        for memory in data:

            if not isinstance(
                memory,
                dict
            ):
                continue

            values = set(
                memory.get(
                    "mary_values",
                    []
                )
            )

            for value in domain_values:

                values.add(value)

            memory[
                "mary_values"
            ] = sorted(
                list(values)
            )

            memory[
                "mary_processed"
            ] = True

            memory[
                "mary_version"
            ] = "2.0"

            memory[
                "mary_domain"
            ] = domain_name

            memory[
                "mary_importance"
            ] = memory.get(
                "salience_score",
                0
            )

            VALUES_ASSIGNED += len(
                domain_values
            )

            MEMORIES_PROCESSED += 1

            changed = True

        if changed:

            with open(
                file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    data,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

        FILES_PROCESSED += 1

    except Exception as e:

        print(
            f"FAILED: {file.name}"
        )

        print(e)

print()
print(
    "=== MARY FULL DOMAIN PASS ==="
)
print()

print(
    f"Files Processed: {FILES_PROCESSED}"
)

print(
    f"Memories Processed: {MEMORIES_PROCESSED}"
)

print(
    f"Values Assigned: {VALUES_ASSIGNED}"
)

print(
    "Version: 2.0"
)

print()
print(
    "Mary Cognition Pass Complete"
)
