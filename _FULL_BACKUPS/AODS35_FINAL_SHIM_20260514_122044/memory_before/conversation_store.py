from datetime import datetime

from core.json_store import (
    safe_load_json,
    safe_save_json,
)

from core.paths import (
    CONVERSATION_FILE,
)

from memory.memory_audit import (
    audit_memory_event,
)


def save_conversation_turn(
    user_msg,
    assistant_reply
):

    try:

        conversations = safe_load_json(
            CONVERSATION_FILE,
            []
        )

        entry = {

            "timestamp": str(datetime.now()),

            "user": user_msg,

            "assistant": assistant_reply

        }

        conversations.append(entry)

        safe_save_json(
            CONVERSATION_FILE,
            conversations
        )

        audit_memory_event(
            "conversation_save",
            CONVERSATION_FILE,
            {
                "user_chars": len(user_msg),
                "assistant_chars": len(assistant_reply)
            }
        )

    except Exception as e:

        print(
            "CONVERSATION SAVE ERROR:",
            e
        )


def build_recent_conversation_context():

    try:

        conversations = safe_load_json(
            CONVERSATION_FILE,
            []
        )

        if not conversations:
            return ""

        recent = conversations[-10:]

        context = "\n\nRECENT CONVERSATIONS:\n"

        for convo in recent:

            context += (
                "\nUSER: "
                + convo.get("user","")
            )

            context += (
                "\nL: "
                + convo.get("assistant","")
            )

            context += "\n"

        return context

    except Exception as e:

        print(
            "CONVO CONTEXT ERROR:",
            e
        )

        return ""
