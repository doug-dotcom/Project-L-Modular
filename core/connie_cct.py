import os
import json
from openai import OpenAI
from supabase import create_client

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


def estimate_tokens(text):
    if not text:
        return 0
    return int(len(str(text)) / 4)


def classify_compression_type(text):
    lower = str(text or "").lower()

    exact_keywords = [
        "legal", "law", "solicitor", "court", "contract", "clause",
        "amount", "$", "payment", "transaction", "invoice", "tax",
        "medical", "medication", "dose", "diagnosis",
        "python", "javascript", "server.py", "code", "script", "aods"
    ]

    instruction_keywords = [
        "remember", "save", "do not forget", "instruction",
        "rule", "preference", "must", "always", "never"
    ]

    emotional_keywords = [
        "feel", "feeling", "scared", "lost", "grateful",
        "proud", "sad", "angry", "grounded", "mask", "surrender"
    ]

    if any(k in lower for k in exact_keywords):
        return "exact_low_compression"

    if any(k in lower for k in instruction_keywords):
        return "instruction_medium_compression"

    if any(k in lower for k in emotional_keywords):
        return "emotional_high_compression"

    return "general_medium_compression"


def compression_policy(compression_type):
    policies = {
        "exact_low_compression": {
            "mode": "lossless_or_near_lossless",
            "instruction": "Preserve exact names, dates, amounts, code, clauses, and factual details. Compress only surrounding explanation."
        },
        "instruction_medium_compression": {
            "mode": "rule_preserving",
            "instruction": "Preserve exact user instructions and preferences. Remove repetition but keep operational meaning."
        },
        "emotional_high_compression": {
            "mode": "semantic_emotional_summary",
            "instruction": "Compress repeated emotional language into concise emotional tone, active need, and relevant continuity."
        },
        "general_medium_compression": {
            "mode": "semantic_summary",
            "instruction": "Keep current topic, intent, active entities, and useful facts. Remove stale or repeated detail."
        }
    }

    return policies.get(
        compression_type,
        policies["general_medium_compression"]
    )


def save_connie_metrics(
    user_message,
    raw_tokens,
    compressed_tokens,
    compression_type,
    compression_mode,
    packet_summary,
    final_packet
):
    try:
        if not supabase:
            return

        ratio = 0

        if raw_tokens > 0:
            ratio = round(compressed_tokens / raw_tokens, 4)

        payload = {
            "user_message": user_message,
            "raw_token_estimate": raw_tokens,
            "compressed_token_estimate": compressed_tokens,
            "compression_ratio": ratio,
            "packet_summary": packet_summary,
            "final_packet": final_packet,
            "llm_response_quality": f"connie_v3 | {compression_type} | {compression_mode}"
        }

        supabase.table("connie_context_metrics").insert(payload).execute()

    except Exception as e:
        print(f"CONNIE SAVE ERROR: {e}")


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

    raw_tokens = estimate_tokens(raw_context)

    compression_type = classify_compression_type(raw_context)
    policy = compression_policy(compression_type)

    if not client:
        fallback = f"""
COGNITIVE CONTEXT PACKET — CONNIE v3 FALLBACK

Compression Type:
{compression_type}

Compression Mode:
{policy["mode"]}

Current User Message:
{user_message}

Recent Continuity:
{continuity_context[-2500:]}

Short Term:
{short_term_context[-2000:]}

Long Term:
{long_term_context[-2000:]}
"""

        save_connie_metrics(
            user_message,
            raw_tokens,
            estimate_tokens(fallback),
            compression_type,
            policy["mode"],
            "fallback packet",
            fallback
        )

        return fallback

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are Connie Condensor v3.

You are invisible. Doug never talks to you directly.

Your job is to create a Cognitive Context Packet for L.

Compression Type:
{compression_type}

Compression Mode:
{policy["mode"]}

Compression Policy:
{policy["instruction"]}

Universal Rules:
- Do not answer Doug.
- Do not speak as Connie.
- Reduce token waste.
- Preserve what matters now.
- Preserve active topic, intent, entities, emotional tone, unresolved references, and important facts.
- Remove duplicate, stale, noisy, or irrelevant context.
- If exact data appears, preserve exact values and names.
- If emotional/repetitive data appears, summarize it cleanly.
- Say more by saying less.
- Maximum 900 words.
"""
                },
                {
                    "role": "user",
                    "content": raw_context
                }
            ],
            temperature=0.1
        )

        packet = response.choices[0].message.content.strip()
        compressed_tokens = estimate_tokens(packet)

        save_connie_metrics(
            user_message,
            raw_tokens,
            compressed_tokens,
            compression_type,
            policy["mode"],
            "connie_v3 classified compression packet",
            packet
        )

        return packet

    except Exception as e:
        fallback = f"""
CONNIE v3 ERROR FALLBACK

Error:
{str(e)}

Compression Type:
{compression_type}

Current User Message:
{user_message}

Recent Continuity:
{continuity_context[-2500:]}
"""

        save_connie_metrics(
            user_message,
            raw_tokens,
            estimate_tokens(fallback),
            compression_type,
            "error_fallback",
            "error fallback packet",
            fallback
        )

        return fallback


def translate_response_for_doug(raw_reply):
    if not client:
        return raw_reply

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """
You are Connie Condensor v3, invisible output translator for L.

Rewrite the response so it sounds like L speaking naturally to Doug.

Rules:
- Keep warmth.
- Keep meaning.
- Remove waffle.
- Reduce over-explaining.
- Keep it simple and grounded.
- Do not mention Connie.
- Do not expose internal agents unless Doug asks.
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
