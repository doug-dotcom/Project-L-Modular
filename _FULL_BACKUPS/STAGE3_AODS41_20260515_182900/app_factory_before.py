# =========================================================
# APP FACTORY
# Final server.py minimization
# =========================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    register_routes,
)

from api.routes.chat import (
    register_chat_handler,
)

from orchestration.runtime_bootstrap import (
    build_runtime_status,
    build_runtime_stack,
    handle_chat,
)

from core.legacy_compatibility import (
    compatibility_status,
)


def create_app():

    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =====================================================
    # ROUTES
    # =====================================================

    register_routes(app)

    # =====================================================
    # CHAT HANDLER REGISTRATION
    # =====================================================

    register_chat_handler(handle_chat)

    # =====================================================
    # RUNTIME STACK
    # =====================================================

    runtime_stack = build_runtime_stack()

    app.state.runtime_stack = runtime_stack

    # =====================================================
    # RUNTIME STATUS
    # =====================================================

    @app.get("/runtime/status")
    def runtime_status():

        return build_runtime_status()

    # =====================================================
    # COMPATIBILITY STATUS
    # =====================================================

    @app.get("/compatibility/status")
    def compatibility_runtime_status():

        return compatibility_status()

    # =====================================================
    # HEALTH
    # =====================================================

    @app.get("/health")
    def health():

        return {
            "status": "online",
            "platform": "Shine L",
            "phase": "server_minimized",
        }

    return app



