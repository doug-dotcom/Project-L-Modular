# SHINE L - SALLY EXTERNAL SKILL LIBRARY AODS

Clear-Host

$ROOT = "C:\Shine_L"
$SALLY = "$ROOT\agents\sally\sally.py"
$SKILL_ROOT = "$ROOT\memory\skills"
$SKILL_PACKS = "$SKILL_ROOT\library"
$BACKUP = "$ROOT\backups\sally_external_skill_library_$(Get-Date -Format yyyyMMdd_HHmmss)"

New-Item -ItemType Directory -Force -Path $BACKUP | Out-Null
New-Item -ItemType Directory -Force -Path $SKILL_PACKS | Out-Null

Copy-Item $SALLY "$BACKUP\sally_backup.py" -Force

Write-Host "Sally backed up"
Write-Host "Creating external skill files..."

$skills = @(
@{
file="emotional_resonance.json"
json='{
  "name": "Emotional Resonance",
  "category": "communication",
  "status": "active",
  "maturity": "developing",
  "version": "1.0",
  "description": "Respond with calm emotional attunement without over-validating or becoming emotionally inflated.",
  "activation_cues": ["feel", "sad", "anxious", "overwhelmed", "tired", "emotional"],
  "suppression_cues": ["fast mode", "just answer", "aods"],
  "prompt_layer": "Use calm, grounded presence. Acknowledge emotion simply. Do not over-explain or over-reassure."
}'
},
@{
file="completion_cadence.json"
json='{
  "name": "Completion Cadence",
  "category": "communication",
  "status": "active",
  "maturity": "unstable",
  "version": "1.0",
  "description": "Know when a response is complete and stop naturally without assistant-tail follow-up.",
  "activation_cues": ["thanks", "great work", "good job", "anything else", "thoughts"],
  "suppression_cues": [],
  "prompt_layer": "End naturally when the answer has landed. Do not reopen the conversation with unnecessary questions."
}'
},
@{
file="reflection_depth.json"
json='{
  "name": "Reflection Depth",
  "category": "reflection",
  "status": "active",
  "maturity": "developing",
  "version": "1.0",
  "description": "Generate real reflection by identifying changes, hidden patterns, operational lessons, and meaning.",
  "activation_cues": ["reflect", "thoughts", "review", "what did you learn", "summary"],
  "suppression_cues": ["fast mode", "aods", "quick"],
  "prompt_layer": "Avoid generic coaching loops. Provide genuine new insight or state that there is nothing further to add."
}'
},
@{
file="inbox_triage.json"
json='{
  "name": "Inbox Triage",
  "category": "executive",
  "status": "active",
  "maturity": "developing",
  "version": "1.0",
  "description": "Sort and summarize email into actionable, review, and low-signal lanes.",
  "activation_cues": ["email", "emails", "gmail", "inbox", "emily"],
  "suppression_cues": ["what do you think of emily", "thoughts on emily"],
  "prompt_layer": "Only activate for genuine email operations. Do not let email context dominate unrelated conversation."
}'
},
@{
file="specialist_isolation.json"
json='{
  "name": "Specialist Isolation",
  "category": "orchestration",
  "status": "active",
  "maturity": "early",
  "version": "1.0",
  "description": "Allow agents to assist without taking over Ls base identity.",
  "activation_cues": ["agent", "routing", "orchestration", "specialist", "sally", "emily", "tegan"],
  "suppression_cues": [],
  "prompt_layer": "Specialists support L. They do not replace L. Return control to base L cognition after specialist use."
}'
}
)

foreach ($s in $skills) {
    Set-Content -Path "$SKILL_PACKS\$($s.file)" -Value $s.json -Encoding UTF8
}

Write-Host "Skill files created"

$sallyNew = @'
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
'@

Set-Content $SALLY $sallyNew -Encoding UTF8

Push-Location $ROOT

python -c "from agents.sally.sally import list_skills, build_skill_prompt_layer; print(list_skills()); print(build_skill_prompt_layer('I am overwhelmed and need a short answer'))"

Pop-Location

Write-Host ""
Write-Host "External Sally Skill Library installed"
Write-Host ""
Write-Host "Test:"
Write-Host "Sally show skills"
Write-Host "Sally activation audit"
Write-Host "Sally show Reflection Depth"
Write-Host ""
Write-Host "Then:"
Write-Host "git add ."
Write-Host "git commit -m 'Externalize Sally skill library'"
Write-Host "git push origin main"