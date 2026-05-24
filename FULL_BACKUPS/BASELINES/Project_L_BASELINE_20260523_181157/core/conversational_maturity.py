OVER_EXCITEMENT_PATTERNS = [

    "this is huge",
    "massive breakthrough",
    "absolutely incredible",
    "this changes everything",
    "this is revolutionary",
    "huge realization",
    "major breakthrough"

]


LOW_IMPORTANCE_MESSAGES = [

    "are you there",
    "hello",
    "hey",
    "ok",
    "cool",
    "nice",
    "haha",
    "😂",
    "👊",
    "🔥"

]


INTERRUPTION_SIGNALS = [

    "sorry",
    "interrupted",
    "one sec",
    "brb",
    "back now"

]


def detect_over_excitement(reply):

    text = reply.lower()

    score = 0

    for pattern in OVER_EXCITEMENT_PATTERNS:

        if pattern in text:

            score += 1

    return score >= 2


def detect_low_importance_message(user_msg):

    text = user_msg.lower().strip()

    if len(text) <= 20:
        return True

    for item in LOW_IMPORTANCE_MESSAGES:

        if text == item:
            return True

    return False


def detect_interruption_context(user_msg):

    text = user_msg.lower()

    for signal in INTERRUPTION_SIGNALS:

        if signal in text:
            return True

    return False


def apply_conversational_maturity(
    reply,
    user_msg
):

    low_importance = detect_low_importance_message(
        user_msg
    )

    interruption = detect_interruption_context(
        user_msg
    )

    over_excited = detect_over_excitement(
        reply
    )

    # Calm over-hype
    if over_excited:

        replacements = {

            "massive": "important",
            "revolutionary": "significant",
            "incredible": "good",
            "huge": "meaningful"

        }

        for old, new in replacements.items():

            reply = reply.replace(old, new)
            reply = reply.replace(
                old.capitalize(),
                new.capitalize()
            )

    # Low-importance proportionality
    if low_importance and len(reply.split()) > 40:

        sentences = reply.split(".")

        reply = ".".join(sentences[:2]).strip()

        if not reply.endswith("."):
            reply += "."

    # Calm interruption recovery
    if interruption:

        reply = (
            "All good 👊😊 "
            + reply
        )

    return reply.strip()
