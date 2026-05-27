import os
from openai import OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def condense_context(
    user_message: str,
    identity_context: str = "",
    runtime_context: str = "",
    short_term_context: str = "",
    long_term_context: str = "",
    continuity_context: str = ""
) -> str:
    """
    Connie Condensor:
    Invisible CCT layer.
    Compresses noisy context into a clean cognitive packet for L.
    """

    if not client:
        return f"""
COGNITIVE CONTEXT PACKET

Current user message:
{user_message}

Recent continuity:
{continuity_context[-3000:]}

Short-term context:
{short_term_context[-3000:]}

Long-term context:
{long_term_context[-3000:]}
"""

    raw_context = f"""
CURRENT USER MESSAGE:
{user_message}

IDENTITY CONTEXT:
{identity_context}

RUNTIME CONTEXT:
{runtime_context}

SHORT TERM MEMORY:
{short_term_context}

LONG TERM MEMORY:
{long_term_context}

RECENT CONVERSATION CONTINUITY:
{continuity_context}
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """
You are Connie Condensor, an invisible cognitive context translation layer for L.

Your job is NOT to answer Doug.

Your job is to compress noisy memory, continuity, identity, and context into a clean cognitive packet for the main LLM.

Rules:
- Preserve what matters now.
- Remove repetition, noise, stale drift, and irrelevant history.
- Keep current topic, user intent, active people/entities, emotional tone, unresolved references, and useful facts.
- Translate Doug's natural language into clean machine-readable context.
- Keep it concise.
- Do not speak as Connie.
- Do not include unnecessary explanation.
- Maximum 1200 words.
"""
                },
                {
                    "role": "user",
                    "content": raw_context
                }
            ],
            temperature=0.1
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"""
COGNITIVE CONTEXT PACKET FALLBACK

Connie error:
{str(e)}

Current user message:
{user_message}

Recent continuity:
{continuity_context[-3000:]}

Short-term context:
{short_term_context[-3000:]}

Long-term context:
{long_term_context[-3000:]}
"""


def translate_response_for_doug(raw_reply: str) -> str:
    """
    Optional output translation:
    Compresses LLM response back into Doug-friendly L voice.
    """

    if not client:
        return raw_reply

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """
You are Connie Condensor, invisible output translator for L.

Rewrite the response so it sounds like L speaking naturally to Doug.

Rules:
- Keep it clear.
- Keep it grounded.
- Remove waffle.
- Preserve warmth.
- Preserve important meaning.
- Do not mention Connie.
- Do not mention internal agents unless necessary.
- Say more by saying less.
"""
                },
                {
                    "role": "user",
                    "content": raw_reply
                }
            ],
            temperature=0.2
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return raw_reply
