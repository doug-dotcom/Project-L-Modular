# =====================================================
# PROJECT L — CONNIE ADAPTIVE
# AODS-4G-06
#
# Purpose:
# Adaptive compression layer for cognition flow.
# Connie already exists.
# This extends her dynamically.
# =====================================================


# =====================================================
# SAFE TEXT
# =====================================================

def normalize_text(value):

    if value is None:
        return ""

    return str(value).strip()


# =====================================================
# DETERMINE COMPRESSION MODE
# =====================================================

def determine_compression_mode(

    memory_type="episodic",

    salience_score=0.5,

    runtime_state=None

):

    runtime_state = runtime_state or {}

    stress = float(
        runtime_state.get(
            "stress_level",
            0.3
        )
    )

    cognitive = float(
        runtime_state.get(
            "cognitive_load",
            0.3
        )
    )

    memory_type = str(
        memory_type
    ).lower()

    salience_score = float(
        salience_score
    )

    # =================================================
    # HIGH VALUE MEMORIES
    # =================================================

    if memory_type in [

        "identity",
        "procedural"

    ]:

        return "minimal"

    if salience_score >= 0.85:

        return "minimal"

    # =================================================
    # HIGH STRESS
    # =================================================

    if stress >= 0.75:

        return "aggressive"

    # =================================================
    # HIGH COGNITIVE DEPTH
    # =================================================

    if cognitive >= 0.70:

        return "light"

    # =================================================
    # DEFAULT
    # =================================================

    return "balanced"


# =====================================================
# COMPRESS TEXT
# =====================================================

def compress_text(

    text,

    mode="balanced"

):

    text = normalize_text(text)

    if not text:
        return ""

    # =================================================
    # MINIMAL
    # =================================================

    if mode == "minimal":

        return text

    # =================================================
    # LIGHT
    # =================================================

    if mode == "light":

        return text[:1200]

    # =================================================
    # BALANCED
    # =================================================

    if mode == "balanced":

        return text[:700]

    # =================================================
    # AGGRESSIVE
    # =================================================

    if mode == "aggressive":

        return text[:350]

    return text[:700]


# =====================================================
# COMPRESS MEMORY ITEM
# =====================================================

def compress_memory(

    memory,

    runtime_state=None

):

    if not isinstance(memory, dict):

        memory = {
            "content": str(memory)
        }

    memory_type = str(
        memory.get(
            "memory_type",
            "episodic"
        )
    )

    salience_score = float(
        memory.get(
            "salience_score",
            0.5
        )
    )

    mode = determine_compression_mode(

        memory_type=memory_type,

        salience_score=salience_score,

        runtime_state=runtime_state

    )

    content = normalize_text(
        memory.get("content", "")
    )

    compressed = compress_text(

        content,

        mode=mode

    )

    memory["compression_mode"] = mode

    memory["compressed_content"] = compressed

    memory["connie_processed"] = True

    return memory


# =====================================================
# BATCH COMPRESS
# =====================================================

def compress_memory_batch(

    memories,

    runtime_state=None

):

    if not isinstance(memories, list):

        return []

    output = []

    for memory in memories:

        try:

            output.append(

                compress_memory(

                    memory,

                    runtime_state=runtime_state

                )

            )

        except Exception:

            continue

    return output


# =====================================================
# BUILD COMPRESSED CONTEXT
# =====================================================

def build_compressed_context(

    memories,

    runtime_state=None

):

    compressed = compress_memory_batch(

        memories,

        runtime_state=runtime_state

    )

    lines = []

    for memory in compressed:

        text = normalize_text(

            memory.get(
                "compressed_content",
                ""
            )

        )

        if text:

            lines.append(text)

    return "\n\n".join(lines)


# =====================================================
# SUMMARY
# =====================================================

def summarize_connie(memory):

    if not isinstance(memory, dict):

        return "invalid"

    return (

        f"type={memory.get('memory_type')} | "

        f"salience={memory.get('salience_score')} | "

        f"compression={memory.get('compression_mode')}"

    )
