import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IMPORTANCE_FILE = ROOT / "importance.json"

def load_importance():

    try:

        with open(
            IMPORTANCE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return []

def save_importance(data):

    with open(
        IMPORTANCE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )

def add_importance(
    domain,
    score,
    reason
):

    data = load_importance()

    entry = {

        "domain": domain,

        "importance_score": score,

        "reason": reason

    }

    data.append(entry)

    save_importance(data)

    return entry

if __name__ == "__main__":

    result = add_importance(

        "sport",

        90,

        "Hockey has been a lifelong thread connecting military service, competition, belonging and identity."

    )

    print(result)
