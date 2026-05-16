# =========================
# ELLIE MEMORY WRAPPER
# =========================

from memory.memory_engine import build_context
from memory.retrieval import retrieve_context

def run_ellie(user_msg: str):

    # Base memory (facts + session)
    base_context = ""
    try:
        base_context = build_context()
    except Exception as e:
        base_context = f"Base memory unavailable: {e}"

    # Smart retrieval
    try:
        relevant = retrieve_context(user_msg)
    except Exception:
        relevant = []

    smart_context = "Relevant conversations:\n"

    for r in relevant:
        u = r.get("user", "")
        a = r.get("assistant", "")
        smart_context += f"- U: {u}\n  A: {a}\n"

    return f"{base_context}\n\n{smart_context}"
