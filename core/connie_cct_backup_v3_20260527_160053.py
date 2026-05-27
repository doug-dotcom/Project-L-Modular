import os
from openai import OpenAI
from supabase import create_client

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    ""
)

SUPABASE_KEY = (
    os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        ""
    )
    or
    os.getenv(
        "SUPABASE_KEY",
        ""
    )
)

client = OpenAI(
    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
) if SUPABASE_URL and SUPABASE_KEY else None


def estimate_tokens(text):

    if not text:
        return 0

    return int(
        len(str(text)) / 4
    )


def save_connie_metrics(
    user_message,
    raw_tokens,
    compressed_tokens,
    packet_summary,
    final_packet
):

    try:

        if not supabase:
            return

        ratio = 0

        if raw_tokens > 0:
            ratio = round(
                compressed_tokens / raw_tokens,
                4
            )

        payload = {

            "user_message":
                user_message,

            "raw_token_estimate":
                raw_tokens,

            "compressed_token_estimate":
                compressed_tokens,

            "compression_ratio":
                ratio,

            "packet_summary":
                packet_summary,

            "final_packet":
                final_packet

        }

        supabase.table(
            "connie_context_metrics"
        ).insert(
            payload
        ).execute()

    except Exception as e:

        print(
            f"CONNIE SAVE ERROR: {e}"
        )


def condense_context(

    user_message="",
    identity_context="",
    runtime_context="",
    short_term_context="",
    long_term_context="",
    continuity_context=""

):

    raw_context = f"""

USER MESSAGE:
{user_message}

IDENTITY:
{identity_context}

RUNTIME:
{runtime_context}

SHORT TERM:
{short_term_context}

LONG TERM:
{long_term_context}

CONTINUITY:
{continuity_context}

"""

    raw_tokens = estimate_tokens(
        raw_context
    )

    if not client:

        fallback = f"""

COGNITIVE CONTEXT PACKET

Current user message:
{user_message}

Recent continuity:
{continuity_context[-3000:]}

"""

        save_connie_metrics(
            user_message,
            raw_tokens,
            estimate_tokens(fallback),
            "fallback mode",
            fallback
        )

        return fallback

    try:

        response = client.chat.completions.create(

            model=OPENAI_MODEL,

            messages=[

                {

                    "role": "system",

                    "content": """

You are Connie Condensor.

You are an invisible cognitive context translation layer for L.

Your job:
- reduce cognitive entropy
- preserve important meaning
- preserve active continuity
- remove noise
- remove repetition
- preserve emotional relevance
- preserve active entities
- preserve unresolved references

Compress the context into a concise cognitive packet.

Maximum 1200 words.

"""

                },

                {

                    "role": "user",

                    "content": raw_context

                }

            ],

            temperature=0.1

        )

        packet = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        compressed_tokens = (
            estimate_tokens(packet)
        )

        save_connie_metrics(

            user_message,

            raw_tokens,

            compressed_tokens,

            "adaptive compressed packet",

            packet

        )

        return packet

    except Exception as e:

        return f"""

CONNIE ERROR:
{str(e)}

USER MESSAGE:
{user_message}

"""
