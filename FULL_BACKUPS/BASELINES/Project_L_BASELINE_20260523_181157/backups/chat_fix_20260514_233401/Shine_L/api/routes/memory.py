from fastapi import APIRouter

from api.schemas import (
    ChatRequest,
)

router = APIRouter()


MEMORY_AUDIT_HANDLER = None
MEMORY_AUDIT_V2_HANDLER = None
RECALL_HANDLER = None
STORIES_HANDLER = None


def register_memory_handlers(
    audit_handler,
    audit_v2_handler,
    recall_handler,
    stories_handler
):

    global MEMORY_AUDIT_HANDLER
    global MEMORY_AUDIT_V2_HANDLER
    global RECALL_HANDLER
    global STORIES_HANDLER

    MEMORY_AUDIT_HANDLER = audit_handler
    MEMORY_AUDIT_V2_HANDLER = audit_v2_handler
    RECALL_HANDLER = recall_handler
    STORIES_HANDLER = stories_handler


@router.get("/memory/audit")
async def memory_audit():

    return await MEMORY_AUDIT_HANDLER()


@router.get("/memory/audit-v2")
async def memory_audit_v2():

    return await MEMORY_AUDIT_V2_HANDLER()


@router.post("/recall")
async def recall_story(req: ChatRequest):

    return await RECALL_HANDLER(req)


@router.get("/stories")
async def get_stories():

    return await STORIES_HANDLER()
