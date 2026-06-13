from fastapi import APIRouter

from api.schemas import (
    ChatRequest,
)

router = APIRouter()


# ============================================================
# CHAT ROUTE BRIDGE
# ============================================================

CHAT_HANDLER = None


def register_chat_handler(handler):

    global CHAT_HANDLER

    CHAT_HANDLER = handler


@router.post("/chat")
async def chat(req: ChatRequest):

    if CHAT_HANDLER is None:

        return {
            "reply": "❌ Chat handler not registered."
        }

    return await CHAT_HANDLER(req)
