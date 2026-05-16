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

SKILL_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "skills",
    "skill_library.json"
)

os.makedirs(
    os.path.dirname(SKILL_FILE),
    exist_ok=True
)

def _load_skills():
    try:
        if not os.path.exists(SKILL_FILE):
            return []

        with open(SKILL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception as e:
        print("SALLY LOAD ERROR:", e)
        return []

def _save_skills(skills):
    try:
        with open(SKILL_FILE, "w", encoding="utf-8") as f:
            json.dump(
                skills,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:
        print("SALLY SAVE ERROR:", e)

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
        "improve skills",
        "what can you do"
    ]

    return any(t in text for t in triggers)

def skill_audit():
    skills = _load_skills()

    total = len(skills)

    by_category = {}
    by_maturity = {}

    for skill in skills:
        category = skill.get("category", "uncategorized")
        maturity = skill.get("maturity", "unknown")

        by_category[category] = by_category.get(category, 0) + 1
        by_maturity[maturity] = by_maturity.get(maturity, 0) + 1

    reply = "Sally Skills Library\n\n"
    reply += "Total skills: " + str(total) + "\n\n"

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
        reply += "\n"

    return reply

def show_skill_detail(message):
    skills = _load_skills()
    text = message.lower()

    for skill in skills:
        name = skill.get("name", "")

        if name.lower() in text:
            reply = skill.get("name", "Unnamed Skill") + "\n\n"
            reply += "Category: " + skill.get("category", "uncategorized") + "\n"
            reply += "Status: " + skill.get("status", "unknown") + "\n"
            reply += "Maturity: " + skill.get("maturity", "unknown") + "\n"
            reply += "Version: " + skill.get("version", "1.0") + "\n\n"
            reply += "Description:\n"
            reply += skill.get("description", "") + "\n\n"

            strengths = skill.get("strengths", [])
            improve = skill.get("improve", [])
            activation = skill.get("activation", [])

            if strengths:
                reply += "Strengths:\n"
                for item in strengths:
                    reply += "- " + item + "\n"
                reply += "\n"

            if improve:
                reply += "Improvement areas:\n"
                for item in improve:
                    reply += "- " + item + "\n"
                reply += "\n"

            if activation:
                reply += "Activation cues:\n"
                for item in activation:
                    reply += "- " + item + "\n"

            return reply

    return None

def add_or_update_skill(name, category="general", description=""):
    skills = _load_skills()

    for skill in skills:
        if skill.get("name", "").lower() == name.lower():
            skill["description"] = description or skill.get("description", "")
            skill["updated_at"] = datetime.now().isoformat()
            _save_skills(skills)
            return "Updated skill: " + name

    skills.append({
        "name": name,
        "category": category,
        "status": "active",
        "maturity": "early",
        "version": "1.0",
        "description": description,
        "strengths": [],
        "improve": [],
        "activation": [],
        "created_at": datetime.now().isoformat()
    })

    _save_skills(skills)

    return "Added skill: " + name

def handle_skill_request(message: str):
    text = message.lower()

    detail = show_skill_detail(message)
    if detail:
        return detail

    if "audit" in text or "status" in text:
        return skill_audit()

    if "show" in text or "list" in text or "what skills" in text or "available" in text:
        return list_skills()

    return skill_audit()
