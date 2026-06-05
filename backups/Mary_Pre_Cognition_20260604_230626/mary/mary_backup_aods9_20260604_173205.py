import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# =====================================================
# LOAD LIEUTENANT OUTPUTS
# =====================================================

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

# =====================================================
# CAPTAIN MARY
# =====================================================

def process_domain(domain_name):

    result = {

        "domain": domain_name,

        "relationships": [],

        "patterns": [],

        "meanings": [],

        "casefiles": [],

        "timeline": [],

        "narratives": []

    }

    result["relationships"] = load_json(
        ROOT / "rani" / "relationships.json"
    )

    result["patterns"] = load_json(
        ROOT / "paddy" / "patterns.json"
    )

    result["meanings"] = load_json(
        ROOT / "marnie" / "meanings.json"
    )

    result["casefiles"] = load_json(
        ROOT / "casey" / "casefiles.json"
    )

    result["timeline"] = load_json(
        ROOT / "timeline" / "timeline.json"
    )

    result["narratives"] = load_json(
        ROOT / "narrative" / "stories.json"
    )

    return result

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    packet = process_domain(
        "DVA"
    )

    print(
        json.dumps(
            packet,
            indent=2
        )
    )
