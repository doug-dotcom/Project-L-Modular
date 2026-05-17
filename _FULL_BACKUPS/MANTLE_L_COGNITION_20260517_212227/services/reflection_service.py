# =====================================================
# reflection_service.py
# AODS 50
# =====================================================

from datetime import datetime

def build_reflection(user_input):

    return {
        "timestamp": datetime.now().isoformat(),
        "reflection": user_input
    }
