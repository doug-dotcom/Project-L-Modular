COGNITION_PRIORITY = {
    "L": 100,
    "orchestration": 70,
    "specialist": 50,
    "skill": 30
}


STACK_LIMITS = {
    "max_active_specialists": 1,
    "max_visible_skills": 2,
    "max_context_strength": 5
}


ASSISTANT_TAIL_PATTERNS = [
    "feel free to",
    "let me know if",
    "if you'd like",
    "if you want",
    "anything else",
    "is there anything else",
    "i'm here if",
    "if you would like",
    "happy to help further",
    "would you like to explore",
    "let me know what resonates",
    "what would you like to discuss",
    "if there’s anything specific",
    "if there's anything specific",
    "feel free to share"
]


COMPLETION_TRIGGERS = [
    "great work",
    "thanks",
    "awesome",
    "perfect",
    "good job",
    "well done",
    "that makes sense",
    "love it",
    "exactly",
    "beautiful",
    "we did it",
    "nailed it"
]


def enforce_cognition_priority(reply):

    infrastructure_terms = [
        "supabase memory spine",
        "semantic memory",
        "orchestration spine",
        "active skill layer",
        "activation audit",
        "routing status",
        "stack balancing"
    ]

    infrastructure_hits = 0
    lower = reply.lower()

    for term in infrastructure_terms:
        if term in lower:
            infrastructure_hits += 1

    if infrastructure_hits >= 3:
        sentences = reply.split(".")
        cleaned = []

        for sentence in sentences:
            low = sentence.lower()
            suppress = False

            for term in infrastructure_terms:
                if term in low:
                    suppress = True
                    break

            if not suppress:
                cleaned.append(sentence)

        reply = ".".join(cleaned).strip()

    return reply.strip()


def stabilize_stack_visibility(reply):

    lines = reply.splitlines()
    visible_skill_lines = 0
    cleaned = []

    for line in lines:
        lower = line.lower()

        if (
            "skill:" in lower
            or "activation score" in lower
            or "context strength" in lower
        ):
            visible_skill_lines += 1

            if visible_skill_lines > STACK_LIMITS["max_visible_skills"]:
                continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def apply_orchestration_smoothing(reply):

    replacements = {
        "The ecosystem is": "Things are",
        "Orchestration": "Coordination",
        "Specialist routing": "Support systems",
        "Cognitive architecture": "System design",
        "Stack balancing": "Context balancing"
    }

    for old, new in replacements.items():
        reply = reply.replace(old, new)

    return reply


def apply_final_stabilization(reply):

    reply = enforce_cognition_priority(reply)
    reply = stabilize_stack_visibility(reply)
    reply = apply_orchestration_smoothing(reply)

    while "\n\n\n" in reply:
        reply = reply.replace("\n\n\n", "\n\n")

    return reply.strip()


def detect_completion_state(user_msg, assistant_reply):

    text = (user_msg + " " + assistant_reply).lower()
    score = 0

    for trigger in COMPLETION_TRIGGERS:
        if trigger in text:
            score += 1

    if len(assistant_reply.split()) < 120:
        score += 1

    return score >= 2


def suppress_assistant_tail(reply):

    if not reply:
        return reply

    lines = reply.splitlines()
    cleaned = []

    for line in lines:
        lower = line.lower().strip()
        suppress = False

        for pattern in ASSISTANT_TAIL_PATTERNS:
            if pattern in lower:
                suppress = True
                break

        if not suppress:
            cleaned.append(line)

    reply = "\n".join(cleaned).strip()

    reply = reply.replace(
        "If you need anything else, just let me know!",
        ""
    )

    reply = reply.replace("Let me know!", "")
    reply = reply.replace("Feel free to share!", "")

    while "\n\n\n" in reply:
        reply = reply.replace("\n\n\n", "\n\n")

    return reply.strip()


def stabilize_response(reply):

    if not reply:
        return reply

    fixes = {
        "Your name is Tamara": "Your name is Doug Struthers",
        "your name is Tamara": "your name is Doug Struthers",
        "You are Tamara": "You are Doug Struthers",
        "you are Tamara": "you are Doug Struthers",
        "You have a brother named Doug": "You are Doug Struthers",
        "you have a brother named Doug": "you are Doug Struthers",
        "You served as a Family Physician": "You served as a Financial Planner",
        "you served as a Family Physician": "you served as a Financial Planner"
    }

    cleaned = reply

    for wrong, right in fixes.items():
        cleaned = cleaned.replace(wrong, right)

    return cleaned
