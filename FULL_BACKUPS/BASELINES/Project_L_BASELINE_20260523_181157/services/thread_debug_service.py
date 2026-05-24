# =====================================================
# thread_debug_service.py
# AODS 55
# =====================================================

from services.thread_engine_service import (
    load_thread,
    thread_context,
    thread_status
)

def debug_thread(thread_id="default"):

    return {
        "status": thread_status(thread_id),
        "messages": load_thread(thread_id),
        "context": thread_context(thread_id)
    }
