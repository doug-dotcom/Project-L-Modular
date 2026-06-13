import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.coach.coach import run_coach

def build_experience(memory):

    return f"""

Memory Reflection

Content:
{memory.get("content","")}

Subjects:
{memory.get("subjects",[])}

Values:
{memory.get("values",[])}

Patterns:
{memory.get("patterns",[])}

Relationships:
{memory.get("relationships",[])}

Importance:
{memory.get("importance",0)}

Salience:
{memory.get("salience",0)}

Anchor:
{memory.get("anchor",False)}

"""

def run_memory_to_coach(memory):

    experience = build_experience(memory)

    return run_coach(
        experience
    )

if __name__ == "__main__":

    sample = {

        "content":
            "Doug noticed he kept seeking validation from Pauline.",

        "subjects":
            ["Pauline"],

        "values":
            ["Growth","Truth"],

        "patterns":
            ["Validation Seeking"],

        "relationships":
            [],

        "importance":
            80,

        "salience":
            90,

        "anchor":
            True

    }

    result = run_memory_to_coach(
        sample
    )

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )

