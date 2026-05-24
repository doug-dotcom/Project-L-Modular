LAST_SPECIALIST_AGENT = None


SPECIALIST_RESET_TRIGGERS = [

    "?",
    "thanks",
    "thank you",
    "what do you think",
    "thoughts",
    "how do you feel",
    "do you like",
    "great job",
    "awesome",
    "amazing",
    "good work",
    "what happened",
    "explain",
    "why"

]


def reset_specialist_context(user_msg):

    global LAST_SPECIALIST_AGENT

    text = user_msg.lower().strip()

    if any(
        trigger in text
        for trigger in SPECIALIST_RESET_TRIGGERS
    ):

        LAST_SPECIALIST_AGENT = None

        print("")
        print("🧠 SPECIALIST CONTEXT RESET")

        return True

    return False


def specialist_should_route(
    user_msg,
    specialist_name
):

    global LAST_SPECIALIST_AGENT

    reset_specialist_context(user_msg)

    text = user_msg.lower()

    # ================================================
    # BLOCK STICKY RE-ROUTING
    # ================================================

    if LAST_SPECIALIST_AGENT != specialist_name:

        return True

    # ================================================
    # REQUIRE EXPLICIT REFERENCE
    # ================================================

    explicit_terms = {

        "Emily": [
            "email",
            "emails",
            "gmail",
            "inbox",
            "emily"
        ],

        "Callie": [
            "calendar",
            "meeting",
            "appointment",
            "callie"
        ],

        "Tania": [
            "task",
            "todo",
            "reminder",
            "tania"
        ]

    }

    required = explicit_terms.get(
        specialist_name,
        []
    )

    return any(
        r in text
        for r in required
    )


def specialist_complete(name):

    global LAST_SPECIALIST_AGENT

    LAST_SPECIALIST_AGENT = name

    print("")
    print("🧠 SPECIALIST COMPLETED:", name)
