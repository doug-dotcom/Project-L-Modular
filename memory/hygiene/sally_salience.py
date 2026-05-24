# =====================================================
# PRIORITY ENGINE
# =====================================================

ANCHOR_TERMS = [

    "perspective provides clarity",

    "i am what i am",

    "fatherhood",

    "authenticity",

    "project l",

    "emotional understanding"
]

# =====================================================
# SCORE MEMORY
# =====================================================

def score_memory(memory):

    content = str(
        memory.get("content", "")
    ).lower()

    priority = 5

    salience = "medium"

    anchor = False

    for term in ANCHOR_TERMS:

        if term in content:

            priority = 10

            salience = "high"

            anchor = True

    memory["priority"] = priority

    memory["salience"] = salience

    memory["anchor"] = anchor

    return memory

# =====================================================
# RUN SALLY
# =====================================================

def run_sally(memories):

    output = []

    for memory in memories:

        output.append(
            score_memory(memory)
        )

    return output
