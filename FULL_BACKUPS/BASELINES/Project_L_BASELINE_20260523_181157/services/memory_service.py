# =====================================================
# memory_service.py
# AODS 50
# =====================================================

from core.memory_router import (
    load_memory,
    save_memory,
    memory_summary
)

def get_identity():
    return load_memory("identity")

def save_reflection(text):

    item = {
        "type": "reflection",
        "text": text
    }

    return save_memory("reflections", item)

def runtime_memory_status():
    return memory_summary()
