import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_FILE = ROOT / "memory" / "domains.json"

with open(DOMAIN_FILE,"r",encoding="utf-8") as f:
    DOMAINS = json.load(f)

def classify(text):

    text = text.lower()

    scores = {}

    for domain, keywords in DOMAINS.items():

        score = 0

        for keyword in keywords:

            if keyword.lower() in text:
                score += 1

        scores[domain] = score

    best = max(scores,key=scores.get)

    return {
        "domain": best,
        "score": scores[best]
    }


if __name__ == "__main__":

    test = "Alan called about AGR and Gold Card"

    print(classify(test))
