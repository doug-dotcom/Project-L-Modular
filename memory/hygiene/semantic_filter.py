import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "memory"
REPORT_DIR = MEMORY_DIR / "hygiene" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

ASSISTANT_SLUDGE_PATTERNS = [
    r"\bif you('?d| would) like\b",
    r"\blet me know\b",
    r"\bi'?m here to help\b",
    r"\bi'?m here to support\b",
    r"\bfeel free to\b",
    r"\bhope this helps\b",
    r"\bas an ai\b",
    r"\bi appreciate your feedback\b",
    r"\bthank you for sharing\b",
    r"\bthank you for your patience\b",
    r"\bthat sounds fantastic\b",
    r"\bi'?m excited\b",
    r"\bi'?ll work on\b",
    r"\bi will strive\b",
    r"\bi can assist\b",
    r"\bplease let me know\b",
]

LOW_VALUE_PATTERNS = [
    r"^good morning",
    r"^thank you",
    r"^absolutely[!,]?",
    r"^certainly[!,]?",
    r"^sure[!,]?",
    r"^got it[!,]?",
    r"^yes[!,]?",
]

HIGH_VALUE_KEYWORDS = [
    "doug",
    "children",
    "iyla",
    "ashton",
    "luella",
    "mehlia",
    "leah",
    "pauline",
    "recovery",
    "mask",
    "armour",
    "armor",
    "addiction",
    "nervous system",
    "if/when",
    "emotional",
    "identity",
    "dougie",
    "douglas",
    "project l",
    "shine",
    "memory",
    "hockey",
    "army",
    "trauma",
    "schema",
    "meetings",
    "abandonment",
    "family",
]

def normalize_text(text) -> str:

    if text is None:
        return ""

    if isinstance(text, dict):
        try:
            text = json.dumps(text, ensure_ascii=False)
        except Exception:
            text = str(text)

    elif isinstance(text, list):
        try:
            text = " ".join([str(x) for x in text])
        except Exception:
            text = str(text)

    else:
        text = str(text)

    text = re.sub(r"\s+", " ", text).strip()

    return text

def sludge_score(text: str) -> float:
    lowered = text.lower()
    score = 0.0

    for pattern in ASSISTANT_SLUDGE_PATTERNS:
        if re.search(pattern, lowered):
            score += 0.18

    for pattern in LOW_VALUE_PATTERNS:
        if re.search(pattern, lowered):
            score += 0.12

    if len(text) < 80:
        score += 0.15

    if text.count("If ") + text.count("if ") > 4:
        score += 0.08

    if "?" in text and len(text) < 180:
        score += 0.08

    return min(score, 1.0)

def salience_hint(text: str) -> float:
    lowered = text.lower()
    score = 0.0

    for kw in HIGH_VALUE_KEYWORDS:
        if kw in lowered:
            score += 0.08

    if len(text) > 250:
        score += 0.08

    if "realized" in lowered or "realised" in lowered:
        score += 0.12

    if "learned" in lowered or "learnt" in lowered:
        score += 0.08

    if "important" in lowered:
        score += 0.05

    return min(score, 1.0)

def classify_memory(content: str) -> dict:
    content = normalize_text(content)
    s_score = sludge_score(content)
    salience = salience_hint(content)

    if s_score >= 0.45 and salience < 0.35:
        action = "delete_candidate"
        reason = "assistant_sludge_or_low_value"
    elif s_score >= 0.35 and salience >= 0.35:
        action = "compress_candidate"
        reason = "mixed_value_with_assistant_filler"
    elif salience >= 0.45:
        action = "keep_candidate"
        reason = "high_semantic_salience"
    else:
        action = "review_candidate"
        reason = "uncertain_value"

    return {
        "action": action,
        "reason": reason,
        "sludge_score": round(s_score, 3),
        "salience_hint": round(salience, 3),
    }

def load_json_file(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def extract_memories(data):
    if isinstance(data, dict) and isinstance(data.get("memories"), list):
        return data["memories"]

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["items", "data", "queue", "pending"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []

def audit_file(path: Path):
    data = load_json_file(path)
    if data is None:
        return None

    memories = extract_memories(data)
    if not memories:
        return None

    results = []
    counts = {
        "keep_candidate": 0,
        "compress_candidate": 0,
        "review_candidate": 0,
        "delete_candidate": 0,
    }

    for index, mem in enumerate(memories):
        if isinstance(mem, dict):
            content = mem.get("content") or mem.get("text") or mem.get("summary") or ""
        else:
            content = str(mem)

        result = classify_memory(content)
        counts[result["action"]] += 1

        results.append({
            "index": index,
            "action": result["action"],
            "reason": result["reason"],
            "sludge_score": result["sludge_score"],
            "salience_hint": result["salience_hint"],
            "preview": normalize_text(content)[:280],
        })

    return {
        "file": str(path.relative_to(ROOT)),
        "memory_count": len(memories),
        "counts": counts,
        "results": results,
    }

def run_audit():
    targets = []

    for folder in [
        MEMORY_DIR / "domains",
        MEMORY_DIR / "pending",
        MEMORY_DIR
    ]:
        if folder.exists():
            targets.extend(folder.glob("*.json"))

    seen = set()
    unique_targets = []

    for t in targets:
        if t.resolve() not in seen:
            seen.add(t.resolve())
            unique_targets.append(t)

    audits = []

    for path in unique_targets:
        audit = audit_file(path)
        if audit:
            audits.append(audit)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"semantic_hygiene_report_{timestamp}.json"

    summary = {
        "generated_at": datetime.now().isoformat(),
        "mode": "SAFE_AUDIT_ONLY",
        "note": "This report does not modify memory files.",
        "files_audited": len(audits),
        "audits": audits,
    }

    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("")
    print("Semantic hygiene audit complete.")
    print(f"Files audited: {len(audits)}")
    print(f"Report written to: {report_path}")
    print("")

    total = {
        "keep_candidate": 0,
        "compress_candidate": 0,
        "review_candidate": 0,
        "delete_candidate": 0,
    }

    for audit in audits:
        for k, v in audit["counts"].items():
            total[k] += v

    print("Summary:")
    for k, v in total.items():
        print(f"  {k}: {v}")

    return summary

if __name__ == "__main__":
    run_audit()
