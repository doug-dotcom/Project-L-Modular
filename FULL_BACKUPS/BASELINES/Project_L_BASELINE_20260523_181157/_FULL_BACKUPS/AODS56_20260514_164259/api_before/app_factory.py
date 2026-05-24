# ============================================================
# APP FACTORY
# Final server.py minimization
# ============================================================

from fastapi import FastAPI

from api.routes import (
    register_routes,
)

from orchestration.runtime_bootstrap import (
    build_runtime_status,
)

from core.legacy_compatibility import (
    compatibility_status,
)

from orchestration.runtime_bootstrap import (
    build_runtime_stack,
)


def create_app():

    app = FastAPI()

    register_routes(app)

    runtime_stack = build_runtime_stack()

    app.state.runtime_stack = runtime_stack

    # ========================================================
    # RUNTIME STATUS
    # ========================================================

    @app.get("/runtime/status")
    def runtime_status():

        return build_runtime_status()

    # ========================================================
    # COMPATIBILITY STATUS
    # ========================================================

    @app.get("/compatibility/status")
    def compatibility_runtime_status():

        return compatibility_status()

    # ========================================================
    # HEALTH
    # ========================================================

    @app.get("/health")
    def health():

        return {
            "status": "online",
            "platform": "Shine L",
            "phase": "server_minimized"
        }

    return app
