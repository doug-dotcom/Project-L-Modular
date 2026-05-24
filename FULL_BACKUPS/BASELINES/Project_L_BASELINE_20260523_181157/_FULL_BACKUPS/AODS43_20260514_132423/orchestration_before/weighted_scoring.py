def score_cognition_domains(user_msg):

    text = user_msg.lower()

    scores = {

        "Emme": 0,
        "Addie": 0,
        "Millie": 0,
        "Gracie": 0,
        "Noelie": 0,
        "Richie": 0

    }

    emme_words = [
        "overwhelmed",
        "emotional",
        "anxious",
        "panic",
        "peace",
        "chaos",
        "stress",
        "nervous system",
        "feel"
    ]

    addie_words = [
        "organize",
        "tasks",
        "focus",
        "plan",
        "workflow",
        "important things"
    ]

    millie_words = [
        "remember",
        "memory",
        "continuity",
        "save this"
    ]

    gracie_words = [
        "legacy",
        "children",
        "future generations",
        "book",
        "story",
        "preserve"
    ]

    noelie_words = [
        "research",
        "investigate",
        "learn",
        "analysis"
    ]

    richie_words = [
        "reflect",
        "reflection",
        "patterns",
        "growth",
        "lessons"
    ]

    for word in emme_words:

        if word in text:

            scores["Emme"] += 2

    for word in addie_words:

        if word in text:

            scores["Addie"] += 2

    for word in millie_words:

        if word in text:

            scores["Millie"] += 2

    for word in gracie_words:

        if word in text:

            scores["Gracie"] += 2

    for word in noelie_words:

        if word in text:

            scores["Noelie"] += 2

    for word in richie_words:

        if word in text:

            scores["Richie"] += 1

    return scores


def calculate_agent_confidence(user_msg):

    text = user_msg.lower()

    scores = {

        "Fiona": 0,
        "Gracie": 0,
        "Millie": 0,
        "Richie": 0,
        "Noelie": 0,
        "Addie": 0

    }

    finance_terms = [

        "mortgage",
        "income",
        "tax",
        "equity",
        "balance sheet",
        "profit",
        "loss",
        "valuation",
        "interest rate",
        "repayments",
        "dva",
        "insurance"

    ]

    legacy_terms = [

        "legacy",
        "future generations",
        "my story",
        "journal",
        "preserve",
        "reflection"

    ]

    memory_terms = [

        "remember",
        "recall",
        "what do you know",
        "memory audit"

    ]

    reflection_terms = [

        "lesson",
        "growth",
        "pattern",
        "reflection",
        "learning"

    ]

    research_terms = [

        "research",
        "investigate",
        "compare",
        "sources",
        "evidence"

    ]

    task_terms = [

        "task",
        "todo",
        "remind",
        "organize",
        "plan"

    ]

    for term in finance_terms:

        if term in text:

            scores["Fiona"] += 2

    for term in legacy_terms:

        if term in text:

            scores["Gracie"] += 2

    for term in memory_terms:

        if term in text:

            scores["Millie"] += 2

    for term in reflection_terms:

        if term in text:

            scores["Richie"] += 1

    for term in research_terms:

        if term in text:

            scores["Noelie"] += 2

    for term in task_terms:

        if term in text:

            scores["Addie"] += 1

    return scores


def orchestration_summary(scores):

    output = "\n\nACTIVE AGENT CONFIDENCE:\n"

    for agent, score in scores.items():

        if score > 0:

            output += (
                f"- {agent}: "
                f"{score}\n"
            )

    return output


def build_orchestra_context(scores):

    context = "\n\nACTIVE COGNITION DOMAINS:\n"

    for agent, score in scores.items():

        if score > 0:

            context += (
                f"- {agent}: "
                f"{score}\n"
            )

    return context
