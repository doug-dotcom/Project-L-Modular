# ============================================================
# MEMORY LEARNING BRIDGE
# Compatibility bridge for core memory learning modules.
# No live cutover yet.
# ============================================================

try:
    from core.memory_learn import *
except Exception as e:
    print("MEMORY LEARNING BRIDGE IMPORT ERROR:", e)

