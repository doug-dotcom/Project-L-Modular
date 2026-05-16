from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import traceback

app = FastAPI(
    title="Shine_L Runtime",
    version="Stage 3 / AODS 90",
    description="Canonical Shine_L runtime bootstrap"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "system": "Shine_L",
        "status": "online",
        "stage": "Stage 3",
        "seal": "AODS 90"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "runtime": "Shine_L"
    }

try:
    from services.runtime_endpoints import router as runtime_router
    app.include_router(runtime_router)

    RUNTIME_IMPORT_STATUS = {
        "status": "runtime_endpoints_loaded",
        "router_loaded": True
    }

except BaseException as exc:

    IMPORT_ERROR_TYPE = type(exc).__name__
    IMPORT_ERROR_REPR = repr(exc)
    IMPORT_ERROR_TEXT = str(exc)
    IMPORT_ERROR_TRACEBACK = traceback.format_exc()

    RUNTIME_IMPORT_STATUS = {
        "status": "runtime_endpoint_import_failed",
        "router_loaded": False,
        "error_type": IMPORT_ERROR_TYPE,
        "error": IMPORT_ERROR_TEXT,
        "repr": IMPORT_ERROR_REPR,
        "traceback": IMPORT_ERROR_TRACEBACK
    }

    @app.get("/runtime/import-error")
    def runtime_import_error():
        return RUNTIME_IMPORT_STATUS

@app.get("/runtime/bootstrap/status")
def runtime_bootstrap_status():
    return RUNTIME_IMPORT_STATUS



# =====================================================
# EMERGENCY DIRECT UI BRIDGE
# =====================================================

@app.get("/runtime/status")
def direct_runtime_status():
    return {
        "response": "Shine_L runtime online",
        "runtime": "ONLINE",
        "status": "STABLE",
        "cognition": "ACTIVE"
    }

@app.get("/runtime/health")
def direct_runtime_health():
    return {
        "response": "Runtime healthy",
        "runtime": "ONLINE",
        "status": "HEALTHY",
        "cognition": "ACTIVE"
    }

@app.post("/runtime/chat")
def direct_runtime_chat(payload: dict):
    user_message = payload.get("message", "")
    return {
        "response": f"L heard: {user_message}",
        "runtime": "ONLINE",
        "status": "STABLE",
        "cognition": "ACTIVE"
    }
