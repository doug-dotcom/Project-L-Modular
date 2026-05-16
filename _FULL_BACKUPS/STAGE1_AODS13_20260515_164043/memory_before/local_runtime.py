# ============================================================
# LOCAL RUNTIME COMPATIBILITY BRIDGE
# ============================================================

from memory.engine.memory_core import *


def process(*args, **kwargs):

    return {
        "status": "compatibility_process_stub",
        "args": args,
        "kwargs": kwargs
    }


def build_context(*args, **kwargs):

    return {
        "status": "compatibility_context_stub",
        "args": args,
        "kwargs": kwargs
    }