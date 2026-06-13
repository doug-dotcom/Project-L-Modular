from fastapi import (
    APIRouter,
    UploadFile,
    File,
)

router = APIRouter()


UPLOAD_HANDLER = None


def register_upload_handler(handler):

    global UPLOAD_HANDLER

    UPLOAD_HANDLER = handler


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...)
):

    if UPLOAD_HANDLER is None:

        return {
            "status": "error",
            "message": "❌ Upload handler not registered."
        }

    return await UPLOAD_HANDLER(file)
