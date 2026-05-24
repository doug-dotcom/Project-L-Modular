import os
import json
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

SKILL_LIBRARY_DIR = os.path.join(
    ROOT_DIR,
    "memory",
    "skills",
    "library"
)

ACTIVATION_LOG_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "skills",
    "skill_activation_log.json"
)

os.makedirs(SKILL_LIBRARY_DIR, exist_ok=True)

def _load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("SALLY SKILL LOAD ERROR:", path, e)
        return None

def _load_skills():
    skills = []

    try:
        for filename in os.listdir(SKILL_LIBRARY_DIR):
            if not filename.lower().endswith(".json"):
                continue

            path = os.path.join(SKILL_LIBRARY_DIR, filename)
            data = _load_json_file(path)

            if isinstance(data, dict):
                data["_source_file"] = filename
                skills.append(data)

        return skills

    except Exception as e:
        print("SALLY LIBRARY LOAD ERROR:", e)
        return []

def _load_activation_log():
    try:
        if not os.path.exists(ACTIVATION_LOG_FILE):
            return []

        with open(ACTIVATION_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def _save_activation_log(log):
    try:
        with open(ACTIVATION_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log[-500:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("SALLY LOG SAVE ERROR:", e)

def should_handle(message: str) -> bool:
    text = message.lower()

    triggers = [
        "sally",
        "skill",
        "skills",
        "skill library",
        "capability library",
        "what skills",
        "show skills",
        "skill audit",
        "available skills",
        "skill activation"
    ]

    return any(t in text for t in triggers)

def _score_skill(skill, message):
    text = message.lower()
    score = 0

    for cue in skill.get("activation_cues", []):
        if str(cue).lower() in text:
            score += 3

    if skill.get("name", "").lower() in text:
        score += 6

    if skill.get("category", "").lower() in text:
        score += 2

    return score

def _is_suppressed(skill, message):
    text = message.lower()

    for cue in skill.get("suppression_cues", []):
        if str(cue).lower() in text:
            return True

    return False

def search_skills(message, limit=5):
    skills = _load_skills()
    results = []

    for skill in skills:
        if _is_suppressed(skill, message):
            continue

        score = _score_skill(skill, message)

        if score > 0:
            item = dict(skill)
            item["activation_score"] = score
            results.append(item)

    results.sort(
        key=lambda x: x.get("activation_score", 0),
        reverse=True
    )

    return results[:limit]

def build_skill_prompt_layer(message: str):
    matches = search_skills(message)

    if not matches:
        return ""

    layer = "\n\nACTIVE SKILL LAYER:\n"

    for skill in matches:
        layer += "- " + skill.get("name", "Unnamed Skill")
        layer += " | category: " + skill.get("category", "general")
        layer += " | maturity: " + skill.get("maturity", "unknown")
        layer += " | score: " + str(skill.get("activation_score", 0))
        layer += "\n"
        layer += "  Instruction: " + skill.get("prompt_layer", skill.get("description", ""))
        layer += "\n"

    layer += "\nRULE: Use only relevant activated skills. Do not let skill context override L’s base identity.\n"

    log = _load_activation_log()
    log.append({
        "timestamp": datetime.now().isoformat(),
        "message_preview": message[:250],
        "activated": [
            {
                "name": s.get("name"),
                "score": s.get("activation_score"),
                "source": s.get("_source_file")
            }
            for s in matches
        ]
    })
    _save_activation_log(log)

    return layer

def skill_audit():
    skills = _load_skills()

    by_category = {}
    by_maturity = {}

    for skill in skills:
        category = skill.get("category", "uncategorized")
        maturity = skill.get("maturity", "unknown")

        by_category[category] = by_category.get(category, 0) + 1
        by_maturity[maturity] = by_maturity.get(maturity, 0) + 1

    reply = "Sally Skills Library\n\n"
    reply += "Total external skills: " + str(len(skills)) + "\n\n"

    reply += "By category:\n"
    for category, count in sorted(by_category.items()):
        reply += "- " + category + ": " + str(count) + "\n"

    reply += "\nBy maturity:\n"
    for maturity, count in sorted(by_maturity.items()):
        reply += "- " + maturity + ": " + str(count) + "\n"

    return reply

def list_skills():
    skills = _load_skills()

    if not skills:
        return "Sally Skills Library is empty."

    reply = "Sally Skills Library\n\n"

    for skill in skills:
        reply += "- " + skill.get("name", "Unnamed Skill")
        reply += " | " + skill.get("category", "uncategorized")
        reply += " | " + skill.get("maturity", "unknown")
        reply += " | v" + skill.get("version", "1.0")
        reply += " | file: " + skill.get("_source_file", "")
        reply += "\n"

    return reply

def activation_audit():
    log = _load_activation_log()

    if not log:
        return "Sally Activation Audit\n\nNo activations logged yet."

    reply = "Sally Activation Audit\n\n"

    for item in log[-10:]:
        reply += "Time: " + str(item.get("timestamp", "")) + "\n"
        reply += "Activated:\n"

        for active in item.get("activated", []):
            reply += "- " + str(active.get("name", ""))
            reply += " score " + str(active.get("score", ""))
            reply += " source " + str(active.get("source", ""))
            reply += "\n"

        reply += "\n"

    return reply

def show_skill_detail(message):
    text = message.lower()
    skills = _load_skills()

    for skill in skills:
        name = skill.get("name", "")

        if name.lower() in text:
            reply = name + "\n\n"
            reply += "Category: " + skill.get("category", "general") + "\n"
            reply += "Status: " + skill.get("status", "unknown") + "\n"
            reply += "Maturity: " + skill.get("maturity", "unknown") + "\n"
            reply += "Version: " + skill.get("version", "1.0") + "\n"
            reply += "Source file: " + skill.get("_source_file", "") + "\n\n"
            reply += "Description:\n" + skill.get("description", "") + "\n\n"
            reply += "Prompt layer:\n" + skill.get("prompt_layer", "") + "\n"

            return reply

    return None

def handle_skill_request(message: str):
    text = message.lower()

    detail = show_skill_detail(message)
    if detail:
        return detail

    if "activation audit" in text:
        return activation_audit()

    if "activate" in text or "activation" in text:
        layer = build_skill_prompt_layer(message)
        if not layer:
            return "No matching skills activated."
        return layer.strip()

    if "show" in text or "list" in text or "what skills" in text or "available" in text:
        return list_skills()

    return skill_audit()
