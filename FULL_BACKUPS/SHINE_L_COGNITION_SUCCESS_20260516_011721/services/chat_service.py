# =====================================================
# chat_service.py
# AODS 50
# =====================================================

from openai import OpenAI
from services.identity_service import build_system_prompt
from services.memory_context_service import build_memory_context
from services.agent_bus_service import publish_message
from services.thread_engine_service import (
    append_thread,
    thread_context
)

client = OpenAI()

SYSTEM_PROMPT = build_system_prompt()

def build_messages(user_message, memory_context=""):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if memory_context:
        messages.append({
            "role": "system",
            "content": f"Relevant memory: {memory_context}"
        })

    messages.append({
        "role": "user",
        "content": user_message
    })

    return messages

def generate_reply(user_message, memory_context="", thread_id="default"):

    if not memory_context:
        memory_context = build_memory_context()

    append_thread(thread_id, "user", user_message)

    publish_message(
        sender="Doug",
        recipient="L",
        message_type="chat",
        content=user_message,
        priority="normal",
        thread_id=thread_id
    )

    thread_memories = thread_context(thread_id)

    combined_context = f"""
MEMORY CONTEXT:
{memory_context}

THREAD CONTEXT:
{thread_memories}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=build_messages(user_message, combined_context),
        temperature=0.7
    )

    reply = response.choices[0].message.content

    append_thread(thread_id, "assistant", reply)

    publish_message(
        sender="L",
        recipient="Doug",
        message_type="reply",
        content=reply,
        priority="normal",
        thread_id=thread_id
    )

    return reply




