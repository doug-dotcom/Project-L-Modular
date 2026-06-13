from fastapi import APIRouter

from api.schemas import (
    ChatRequest,
)

router = APIRouter()


EMILY_HANDLER = None
BRITTANY_HANDLER = None


def register_direct_agent_handlers(
    emily_handler,
    brittany_handler
):

    global EMILY_HANDLER
    global BRITTANY_HANDLER

    EMILY_HANDLER = emily_handler
    BRITTANY_HANDLER = brittany_handler


@router.post("/emily")
async def emily_direct(req: ChatRequest):

    return await EMILY_HANDLER(req)


@router.post("/brittany")
async def brittany_direct(req: ChatRequest):

    return await BRITTANY_HANDLER(req)
