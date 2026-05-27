# ============================================================
# SHINE L SERVER
# FINAL MINIMIZED COMPATIBILITY HOST
# ============================================================

from api.app_factory import (
    create_app,
)

# ============================================================
# APP
# ============================================================

app = create_app()

# ============================================================
# SERVER ROLE
#
# - compatibility host
# - route registration
# - runtime bridge
#
# Runtime authority:
# - orchestration/
# - memory/
# ============================================================

