import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASE_FILE = ROOT / "casefiles.json"

def load_casefiles():

    if not CASE_FILE.exists():
        return []

    with open(CASE_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_casefiles(data):

    with open(CASE_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def add_casefile(title, summary):

    data = load_casefiles()

    entry = {
        "title": title,
        "summary": summary
    }

    data.append(entry)

    save_casefiles(data)

    return entry

if __name__ == "__main__":

    result = add_casefile(
        "DVA Summary",
        "Current stress is being driven by uncertainty and administrative delay rather than claim failure."
    )

    print(result)
