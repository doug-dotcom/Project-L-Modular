# ============================================================
# MEMORY ENGINE BRIDGE
# Compatibility bridge for legacy memory engine location.
# No deletion. No forced cutover.
# ============================================================

try:
    from memory.local_runtime import (
        process,
        build_context
    )
except Exception as e:
    print("MEMORY ENGINE BRIDGE IMPORT ERROR:", e)

    def process(user_msg):
        return None

    def build_context():
        return ""
