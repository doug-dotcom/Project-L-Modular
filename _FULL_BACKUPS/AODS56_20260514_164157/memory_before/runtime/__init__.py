import time

_last_input = None
_last_time = None

def detect_outcome(current_input):
    global _last_input, _last_time

    now = time.time()

    if _last_input is None:
        _last_input = current_input
        _last_time = now
        return None

    time_diff = now - _last_time

    current = current_input.lower()
    previous = _last_input.lower()

    # Improvement
    if any(w in previous for w in ["overwhelmed", "angry", "stressed"]) and not any(w in current for w in ["overwhelmed", "angry", "stressed"]):
        outcome = "worked"

    # Same state / rapid repeat
    elif current == previous or time_diff < 10:
        outcome = "failed"

    else:
        outcome = None

    _last_input = current_input
    _last_time = now

    return outcome

