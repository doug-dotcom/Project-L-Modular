import json
from pathlib import Path
from datetime import datetime

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

LOG_DIR = ROOT / "memory" / "consequence_logs"

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

# =====================================================
# BASELINE WEIGHTS
# =====================================================

BASELINE = {

    "truthfulness": 0.95,
    "relevance": 0.90,
    "continuity": 0.88,
    "emotional_alignment": 0.85,
    "noise_ratio": 0.20,
    "drift_risk": 0.10,
    "hallucination_risk": 0.10,
    "user_experience": 0.90

}

# =====================================================
# SCORE RESPONSE
# =====================================================

def score_response(
    user_message: str,
    ai_response: str
):

    response = (ai_response or "").lower()

    # =============================================
    # BASIC SCORES
    # =============================================

    truthfulness = 0.90
    relevance = 0.90
    continuity = 0.85
    emotional_alignment = 0.85
    user_experience = 0.88

    noise_ratio = 0.10
    drift_risk = 0.05
    hallucination_risk = 0.05

    # =============================================
    # SIMPLE HEURISTICS
    # =============================================

    if len(response) < 30:
        relevance -= 0.20

    if "i don't know" in response:
        truthfulness += 0.05

    if "latest news" in response:
        continuity -= 0.05

    if "random" in response:
        noise_ratio += 0.10

    # =============================================
    # OVERALL SCORE
    # =============================================

    overall = round(

        (
            truthfulness +
            relevance +
            continuity +
            emotional_alignment +
            user_experience
        ) / 5,

        3

    )

    # =============================================
    # BUILD RESULT
    # =============================================

    result = {

        "timestamp":
            str(datetime.now()),

        "truthfulness":
            round(truthfulness, 3),

        "relevance":
            round(relevance, 3),

        "continuity":
            round(continuity, 3),

        "emotional_alignment":
            round(emotional_alignment, 3),

        "user_experience":
            round(user_experience, 3),

        "noise_ratio":
            round(noise_ratio, 3),

        "drift_risk":
            round(drift_risk, 3),

        "hallucination_risk":
            round(hallucination_risk, 3),

        "overall":
            overall

    }

    return result

# =====================================================
# SAVE SCORE
# =====================================================

def save_score(result):

    file = LOG_DIR / "consequence_scores.jsonl"

    with open(
        file,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(result)
            + "\n"
        )

# =====================================================
# EVALUATE RESPONSE
# =====================================================

def evaluate(
    user_message,
    ai_response
):

    result = score_response(
        user_message,
        ai_response
    )

    save_score(result)

    return result

# =====================================================
# DRIFT CHECK
# =====================================================

def drift_detected(result):

    if result["drift_risk"] > 0.30:
        return True

    if result["hallucination_risk"] > 0.30:
        return True

    if result["noise_ratio"] > 0.50:
        return True

    return False
