from datetime import datetime

from core.json_store import (
    safe_load_json,
    safe_save_json,
)

from core.paths import (
    INVISIBLE_ORCHESTRA_LOG,
)


INVISIBLE_ORCHESTRA_MODE = True


VISIBLE_ORCHESTRA_TRIGGERS = [
    "ecosystem status",
    "show agents",
    "agent status",
    "which agent",
    "show orchestration",
    "debug agents",
    "diagnostic",
    "tegan show"
]


def wants_visible_orchestra(message: str) -> bool:

    text = message.lower()

    return any(
        trigger in text
        for trigger in VISIBLE_ORCHESTRA_TRIGGERS
    )


def log_orchestra_event(
    agent_name,
    user_msg,
    agent_reply
):

    try:

        logs = safe_load_json(
            INVISIBLE_ORCHESTRA_LOG,
            []
        )

        logs.append(
            {
                "timestamp": str(datetime.now()),
                "agent": agent_name,
                "user": user_msg,
                "agent_reply": agent_reply
            }
        )

        safe_save_json(
            INVISIBLE_ORCHESTRA_LOG,
            logs
        )

    except Exception as e:

        print(
            "ORCHESTRA LOG ERROR:",
            e
        )


def strip_agent_headers(reply: str) -> str:

    if not reply:

        return ""

    text = reply.strip()

    headers = [
        "# 🧠 Millie Memory Keeper",
        "# ❤️ Emme Emotional Support",
        "# ✅ Addie Task Execution",
        "# 📖 Gracie Legacy Builder",
        "# 🌐 Noelie Knowledge Research",
        "# 🪞 Richie Reflective Learning",
        "# 🔗 Tegan Integration Spine",
        "# 💬 Winnie WhatsApp Cognition",
        "# 💰 Fiona Finance Cognition",
        "🧠 Millie Memory Keeper:",
        "❤️ Emme Emotional Support:",
        "✅ Addie Task Execution:",
        "📖 Gracie Legacy Builder:",
        "🌐 Noelie Knowledge Research:",
        "🪞 Richie Reflective Learning:",
        "🔗 Tegan Integration Spine:",
        "💬 Winnie WhatsApp:",
        "💰 Fiona Finance:",
        "📧 Emily Email:",
        "📅 Callie Calendar:",
        "✅ Tania Tasks:",
        "🌐 Brittany Browser:"
    ]

    for h in headers:

        text = text.replace(h, "")

    return text.strip()


def compose_l_response(
    user_msg,
    agent_name,
    agent_reply
):

    clean_reply = strip_agent_headers(
        agent_reply
    )

    if wants_visible_orchestra(user_msg):

        return (
            agent_name
            + ":\n\n"
            + clean_reply
        )

    return clean_reply
