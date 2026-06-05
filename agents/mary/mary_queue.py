import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN_DIR = ROOT / "memory" / "domains"

def load_json(path):

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return []

def get_queue():

    queue = []

    files = DOMAIN_DIR.glob("*.json")

    for file in files:

        data = load_json(file)

        if not isinstance(data,list):
            continue

        for memory in data:

            if memory.get(
                "mary_processed",
                False
            ) == False:

                queue.append({

                    "domain":
                        file.stem,

                    "memory":
                        memory

                })

    return queue

if __name__ == "__main__":

    queue = get_queue()

    print(
        f"QUEUE SIZE: {len(queue)}"
    )

    print()

    for item in queue[:5]:

        print(
            item["domain"]
        )

        print(
            item["memory"]
            .get(
                "content",
                ""
            )[:120]
        )

        print("-"*40)
