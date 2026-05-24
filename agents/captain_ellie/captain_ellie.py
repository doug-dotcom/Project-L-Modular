# =====================================================
# CAPTAIN ELLIE
# SHORT-TERM MEMORY CONDUCTOR
# =====================================================

def build_runtime_context(
    short_term_context,
    domain
):

    context_packet = f"""

ACTIVE DOMAIN:
{domain}

ACTIVE SHORT-TERM MEMORY:
{short_term_context}

INSTRUCTIONS:
- Maintain conversational continuity
- Stay focused on current domain
- Use recent conversational flow
- Prioritize active short-term memory
- Respond naturally and contextually
"""

    return context_packet

