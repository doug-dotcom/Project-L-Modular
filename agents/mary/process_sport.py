import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SPORT_FILE = (
    ROOT
    / "memory"
    / "domains"
    / "sport.json"
)

def process_memory(memory):

    content = (
        str(
            memory.get(
                "content",
                ""
            )
        )
        .lower()
    )

    values = []

    if "hockey" in content:

        values.extend([
            "Connection",
            "Commitment"
        ])

    if "army" in content:

        values.append(
            "Discipline"
        )

    if "queensland" in content:

        values.append(
            "Achievement"
        )

    if "team" in content:

        values.append(
            "Belonging"
        )

    values = sorted(
        list(
            set(values)
        )
    )

    memory[
        "mary_processed"
    ] = True

    memory[
        "mary_version"
    ] = "1.0"

    memory[
        "mary_values"
    ] = values

    memory[
        "mary_importance"
    ] = memory.get(
        "salience_score",
        0
    )

    return memory

def main():

    with open(
        SPORT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    processed = 0

    for memory in data:

        if not isinstance(
            memory,
            dict
        ):
            continue

        process_memory(
            memory
        )

        processed += 1

    with open(
        SPORT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(
        "=== MARY SPORT ENGINE ==="
    )
    print()

    print(
        f"Processed: {processed}"
    )

    print(
        f"File: {SPORT_FILE}"
    )

if __name__ == "__main__":

    main()
