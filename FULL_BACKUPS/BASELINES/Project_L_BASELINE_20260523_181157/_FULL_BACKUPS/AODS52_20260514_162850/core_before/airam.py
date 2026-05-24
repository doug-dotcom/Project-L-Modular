# =========================
# AIRAM — UPDATED FOR ELLIE
# =========================

def run_airam(user_input):

    text = user_input.lower()

    # SIMPLE STATE DETECTION
    if "overwhelmed" in text:
        awareness = "You're feeling overwhelmed"
        act = "Pick ONE task only. Ignore everything else."

    elif "angry" in text:
        awareness = "You're feeling angry"
        act = "Do not react. Step away and reset."

    elif "sad" in text:
        awareness = "You're feeling sad"
        act = "Take a small step. Stay gentle with yourself."

    elif "lost" in text:
        awareness = "You're feeling lost"
        act = "Choose the smallest possible next step."

    else:
        awareness = "Check in – what are you feeling?"
        act = "Pick ONE simple next step. Forward, not perfect."

    interrupt = "Pause. Don’t run the old loop."
    regulate = "Breathe: in 4 seconds, out 6 seconds x 4 rounds"
    maintain = "Stay clean. Don’t re-loop."

    return {
        "A": awareness,
        "I": interrupt,
        "R": regulate,
        "A2": act,
        "M": maintain
    }
