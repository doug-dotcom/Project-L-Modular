
from memory.retrieval.memory_retriever import retrieve_memory_context
# =========================================================
# APP FACTORY
# Final server.py minimization
# =========================================================

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
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


def runtime_provenance_headers():
    values = {
        "owner": os.getenv("RAILWAY_GIT_REPO_OWNER"),
        "repo": os.getenv("RAILWAY_GIT_REPO_NAME"),
        "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA"),
        "branch": os.getenv("RAILWAY_GIT_BRANCH"),
        "deployment": os.getenv("RAILWAY_DEPLOYMENT_ID"),
        "service": os.getenv("RAILWAY_SERVICE_NAME"),
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME"),
    }
    if not all(values.values()):
        return {}
    return {
        "X-Shine-Runtime-Provider": "railway",
        "X-Shine-Runtime-Repository": f"{values['owner']}/{values['repo']}",
        "X-Shine-Runtime-Commit": values["commit"],
        "X-Shine-Runtime-Branch": values["branch"],
        "X-Shine-Runtime-Deployment": values["deployment"],
        "X-Shine-Runtime-Service": values["service"],
        "X-Shine-Runtime-Environment": values["environment"],
    }




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

        return JSONResponse(
            {
                "status": "online",
                "platform": "Shine L",
                "phase": "server_minimized",
            },
            headers=runtime_provenance_headers(),
        )

'" + $HealthEndpoint + @'

    return app





