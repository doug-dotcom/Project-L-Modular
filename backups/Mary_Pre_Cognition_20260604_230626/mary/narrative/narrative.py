import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STORY_FILE = ROOT / "stories.json"

def load_stories():

    if not STORY_FILE.exists():
        return []

    with open(STORY_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_stories(data):

    with open(STORY_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def add_story(title, narrative):

    data = load_stories()

    entry = {
        "title": title,
        "narrative": narrative
    }

    data.append(entry)

    save_stories(data)

    return entry

if __name__ == "__main__":

    result = add_story(
        "DVA Transition",
        "Doug is progressing through multiple major life transitions and is currently seeking certainty while several important processes move toward resolution."
    )

    print(result)
