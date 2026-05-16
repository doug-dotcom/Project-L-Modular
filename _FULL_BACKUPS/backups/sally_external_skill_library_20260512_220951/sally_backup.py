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

    if "activation" in text:
        return handle_activation_request(message)

    if "audit" in text or "status" in text:
        return skill_audit()

    if "show" in text or "list" in text or "what skills" in text or "available" in text:
        return list_skills()

    return skill_audit()

# =====================================================
# SALLY SKILL ACTIVATION ENGINE
# =====================================================

ACTIVATION_LOG_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "skills",
    "skill_activation_log.json"
)

def _load_activation_log():
    try:
        if not os.path.exists(ACTIVATION_LOG_FILE):
            return []

        with open(ACTIVATION_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception as e:
        print("SALLY ACTIVATION LOG LOAD ERROR:", e)
        return []

def _save_activation_log(log):
    try:
        with open(ACTIVATION_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                log,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:
        print("SALLY ACTIVATION LOG SAVE ERROR:", e)

def detect_skill_context(message: str):
    text = message.lower()

    context = {
        "mode": "normal",
        "emotional_load": "low",
        "needs_reflection": False,
        "needs_memory": False,
        "needs_email": False,
        "needs_fast": False,
        "needs_orchestration": False,
        "needs_trust": False
    }

    if any(w in text for w in ["overwhelmed", "panic", "anxious", "sad", "stressed", "exhausted", "tired"]):
        context["emotional_load"] = "high"
        context["mode"] = "emotional"

    if any(w in text for w in ["fast", "quick", "just the answer", "short", "aods"]):
        context["needs_fast"] = True
        context["mode"] = "fast"

    if any(w in text for w in ["thoughts", "reflect", "review", "what did you learn", "anything else"]):
        context["needs_reflection"] = True

    if any(w in text for w in ["remember", "recall", "memory", "what do you know"]):
        context["needs_memory"] = True

    if any(w in text for w in ["email", "emails", "gmail", "inbox", "emily"]):
        context["needs_email"] = True

    if any(w in text for w in ["agent", "routing", "orchestration", "tegan", "sally", "skills"]):
        context["needs_orchestration"] = True

    if any(w in text for w in ["audit", "status", "inspect", "debug", "show"]):
        context["needs_trust"] = True

    return context

def score_skill_activation(skill, context, message):
    score = 0
    text = message.lower()

    name = skill.get("name", "").lower()
    category = skill.get("category", "").lower()
    activation = skill.get("activation", [])

    for cue in activation:
        if str(cue).lower() in text:
            score += 3

    if context["emotional_load"] == "high" and "emotional" in name:
        score += 5

    if context["needs_fast"] and "cognitive load" in name:
        score += 5

    if context["needs_reflection"] and category == "reflection":
        score += 5

    if context["needs_memory"] and category == "memory":
        score += 5

    if context["needs_email"] and "inbox" in name:
        score += 5

    if context["needs_orchestration"] and category == "orchestration":
        score += 5

    if context["needs_trust"] and category == "trust":
        score += 5

    return score

def suppress_skill(skill, context, message):
    name = skill.get("name", "").lower()

    if context["mode"] == "fast":
        if "reflection depth" in name:
            return True

        if "context-aware prompting" in name:
            return True

    if context["needs_email"] is False:
        if "inbox triage" in name:
            return True

    if context["emotional_load"] == "low":
        if "emotional resonance" in name and context["needs_reflection"] is False:
            return True

    return False

def activate_skills_for_message(message: str):
    skills = _load_skills()
    context = detect_skill_context(message)

    activated = []
    suppressed = []

    for skill in skills:
        if suppress_skill(skill, context, message):
            suppressed.append(skill.get("name", "Unnamed Skill"))
            continue

        score = score_skill_activation(skill, context, message)

        if score > 0:
            item = dict(skill)
            item["activation_score"] = score
            activated.append(item)

    activated.sort(
        key=lambda x: x.get("activation_score", 0),
        reverse=True
    )

    activated = activated[:5]

    log = _load_activation_log()

    log.append({
        "timestamp": datetime.now().isoformat(),
        "message_preview": message[:250],
        "context": context,
        "activated": [
            {
                "name": x.get("name"),
                "score": x.get("activation_score")
            }
            for x in activated
        ],
        "suppressed": suppressed
    })

    _save_activation_log(log[-500:])

    return {
        "context": context,
        "activated": activated,
        "suppressed": suppressed
    }

def build_skill_prompt_layer(message: str):
    result = activate_skills_for_message(message)

    activated = result.get("activated", [])
    suppressed = result.get("suppressed", [])
    context = result.get("context", {})

    if not activated:
        return ""

    layer = "\n\nACTIVE SKILL LAYER:\n"
    layer += "Context mode: " + str(context.get("mode", "normal")) + "\n\n"

    for skill in activated:
        layer += "- " + skill.get("name", "Unnamed Skill")
        layer += " | maturity: " + skill.get("maturity", "unknown")
        layer += " | score: " + str(skill.get("activation_score", 0))
        layer += "\n"
        layer += "  Use this skill by: "
        layer += skill.get("description", "")
        layer += "\n"

        improve = skill.get("improve", [])
        if improve:
            layer += "  Watch for: " + "; ".join(improve[:2]) + "\n"

    if suppressed:
        layer += "\nSUPPRESSED SKILLS THIS TURN:\n"
        for item in suppressed[:6]:
            layer += "- " + item + "\n"

    layer += "\nRULE: Use only the activated skills that fit this turn. Do not let specialist skills dominate unrelated conversation.\n"

    return layer

def activation_audit():
    log = _load_activation_log()

    if not log:
        return "Sally Activation Audit\n\nNo activations logged yet."

    recent = log[-10:]

    reply = "Sally Activation Audit\n\n"

    for item in recent:
        reply += "Time: " + str(item.get("timestamp", "")) + "\n"
        reply += "Mode: " + str(item.get("context", {}).get("mode", "normal")) + "\n"

        activated = item.get("activated", [])
        suppressed = item.get("suppressed", [])

        reply += "Activated:\n"

        if activated:
            for a in activated:
                reply += "- " + str(a.get("name", "")) + " score " + str(a.get("score", "")) + "\n"
        else:
            reply += "- none\n"

        if suppressed:
            reply += "Suppressed:\n"
            for s in suppressed[:5]:
                reply += "- " + str(s) + "\n"

        reply += "\n"

    return reply

def handle_activation_request(message: str):
    text = message.lower()

    if "activation audit" in text or "skill activation" in text:
        return activation_audit()

    result = activate_skills_for_message(message)

    reply = "Sally Skill Activation\n\n"

    reply += "Mode: " + result["context"].get("mode", "normal") + "\n\n"

    reply += "Activated skills:\n"

    if result["activated"]:
        for skill in result["activated"]:
            reply += "- " + skill.get("name", "Unnamed Skill")
            reply += " score " + str(skill.get("activation_score", 0))
            reply += "\n"
    else:
        reply += "- none\n"

    reply += "\nSuppressed skills:\n"

    if result["suppressed"]:
        for item in result["suppressed"][:8]:
            reply += "- " + item + "\n"
    else:
        reply += "- none\n"

    return reply


