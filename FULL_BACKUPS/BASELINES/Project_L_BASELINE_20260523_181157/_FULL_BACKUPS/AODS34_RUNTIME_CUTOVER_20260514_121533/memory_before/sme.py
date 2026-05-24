from datetime import datetime
from .storage import load_history, save_history
from .profile import update_profile, load_profile
from .tagging import tag_message
from .scoring import score_message
from .retrieval import retrieve_context
from .proactive import proactive_check
from .state_memory import build_state, log_state

def store_interaction(user_input: str, assistant_output: str):
    hist = load_history()
    tags = tag_message(user_input)
    importance = score_message(user_input, tags)
    state = build_state(user_input)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user": user_input,
        "assistant": assistant_output,
        "tags": tags,
        "importance": importance,
        "state": state
    }
    hist.append(entry)
    save_history(hist)
    update_profile(user_input)
    log_state(state)
    return entry

def get_context(user_input: str):
    ctx = retrieve_context(user_input, k=5)
    lines = []
    for h in ctx:
        lines.append(f"User: {h.get('user','')}")
        lines.append(f"Assistant: {h.get('assistant','')}")
    return "\\n".join(lines)

def get_profile():
    return load_profile()

def proactive():
    return proactive_check()
