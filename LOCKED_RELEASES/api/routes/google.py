from fastapi import (
    APIRouter,
    Request,
)

from fastapi.responses import (
    RedirectResponse,
    HTMLResponse,
)

router = APIRouter()


GOOGLE_STATUS_HANDLER = None
GOOGLE_START_HANDLER = None
GOOGLE_CALLBACK_HANDLER = None
GOOGLE_RESET_HANDLER = None


def register_google_handlers(
    status_handler,
    start_handler,
    callback_handler,
    reset_handler
):

    global GOOGLE_STATUS_HANDLER
    global GOOGLE_START_HANDLER
    global GOOGLE_CALLBACK_HANDLER
    global GOOGLE_RESET_HANDLER

    GOOGLE_STATUS_HANDLER = status_handler
    GOOGLE_START_HANDLER = start_handler
    GOOGLE_CALLBACK_HANDLER = callback_handler
    GOOGLE_RESET_HANDLER = reset_handler


@router.get("/google/status")
async def google_connection_status():

    return await GOOGLE_STATUS_HANDLER()


@router.get("/google/auth/start")
async def google_auth_start():

    return await GOOGLE_START_HANDLER()


@router.get("/google/auth/callback")
async def google_auth_callback(
    request: Request
):

    return await GOOGLE_CALLBACK_HANDLER(request)


@router.get("/google/auth/reset")
async def google_auth_reset():

    return await GOOGLE_RESET_HANDLER()
