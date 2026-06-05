import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOMAIN_DIR = ROOT / "memory" / "domains"

TOTAL_FILES = 0
TOTAL_MEMORIES = 0
TOTAL_UPDATED = 0

DEFAULT_FIELDS = {

    "mary_processed": False,

    "mary_version": None,

    "mary_values": [],

    "mary_importance": 0

}

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

        changed = False

        for memory in data:

            if not isinstance(
                memory,
                dict
            ):
                continue

            TOTAL_MEMORIES += 1

            for key, value in DEFAULT_FIELDS.items():

                if key not in memory:

                    memory[key] = value

                    changed = True

                    TOTAL_UPDATED += 1

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

        TOTAL_FILES += 1

    except Exception as e:

        print(
            f"FAILED: {file.name}"
        )

        print(e)

print()
print("=== MARY ENRICHMENT PASS ===")
print()

print(
    f"Files Scanned: {TOTAL_FILES}"
)

print(
    f"Memories Seen: {TOTAL_MEMORIES}"
)

print(
    f"Fields Added: {TOTAL_UPDATED}"
)

print()
print("Mary fields ready.")
