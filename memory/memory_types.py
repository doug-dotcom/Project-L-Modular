# =====================================================
# PROJECT L — MEMORY TYPES
# AODS-4G-04
#
# Purpose:
# Formalize memory categories for cognition routing.
# Does NOT replace current memory systems.
# Adds structured cognition classification.
# =====================================================


MEMORY_TYPES = [

    "episodic",

    "semantic",

    "procedural",

    "emotional",

    "identity"
]


# =====================================================
# DETECT MEMORY TYPE
# =====================================================

def detect_memory_type(content):

    text = str(content).lower()

    # =================================================
    # IDENTITY
    # =================================================

    identity_terms = [

        "i am",
        "my values",
        "my philosophy",
        "identity",
        "truth mode",
        "project l",
        "shine"

    ]

    for term in identity_terms:

        if term in text:

            return "identity"

    # =================================================
    # EMOTIONAL
    # =================================================

    emotional_terms = [

        "felt",
        "emotion",
        "scared",
        "panic",
        "nightmare",
        "triggered",
        "unsafe",
        "mental health",
        "ptsd",
        "anxiety"

    ]

    for term in emotional_terms:

        if term in text:

            return "emotional"

    # =================================================
    # PROCEDURAL
    # =================================================

    procedural_terms = [

        "how to",
        "steps",
        "process",
        "workflow",
        "aods",
        "install",
        "patch",
        "run this"

    ]

    for term in procedural_terms:

        if term in text:

            return "procedural"

    # =================================================
    # SEMANTIC
    # =================================================

    semantic_terms = [

        "research",
        "concept",
        "principle",
        "theory",
        "architecture",
        "cognition",
        "understanding"

    ]

    for term in semantic_terms:

        if term in text:

            return "semantic"

    # =================================================
    # DEFAULT
    # =================================================

    return "episodic"


# =====================================================
# ANNOTATE MEMORY
# =====================================================

def annotate_memory_type(memory):

    if not isinstance(memory, dict):

        memory = {
            "content": str(memory)
        }

    content = str(
        memory.get("content", "")
    )

    memory["memory_type"] = (
        detect_memory_type(content)
    )

    return memory


# =====================================================
# SUMMARY
# =====================================================

def summarize_memory_type(memory):

    if not isinstance(memory, dict):

        return "unknown"

    return str(
        memory.get(
            "memory_type",
            "unknown"
        )
    )
