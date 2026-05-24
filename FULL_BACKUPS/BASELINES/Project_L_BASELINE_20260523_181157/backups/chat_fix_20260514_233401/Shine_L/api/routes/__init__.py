# ============================================================
# API ROUTER REGISTRATION
# Phase 13 - Server.py Collapse
# ============================================================

from api.routes.chat import (
    router as chat_router,
)

from api.routes.upload import (
    router as upload_router,
)

from api.routes.google import (
    router as google_router,
)

from api.routes.memory import (
    router as memory_router,
)

from api.routes.direct_agents import (
    router as direct_agents_router,
)

try:
    from api.routes.system import (
        router as system_router,
    )
except Exception:
    system_router = None


def register_routes(app):

    if system_router:
        app.include_router(system_router)

    app.include_router(chat_router)
    app.include_router(upload_router)
    app.include_router(google_router)
    app.include_router(memory_router)
    app.include_router(direct_agents_router)
