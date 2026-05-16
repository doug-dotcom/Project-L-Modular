from orchestration.runtime_engine import RuntimeEngine
from orchestration.tegan_runtime import MajorTeganRuntime

try:
    from memory.orchestrator import memory_orchestration_status
except Exception:
    def memory_orchestration_status():
        return {"status": "unavailable"}

try:
    from orchestration.active_registry import get_active_captains
except Exception:
    def get_active_captains():
        return []


def build_runtime_stack():

    runtime_engine = RuntimeEngine()
    tegan_runtime = MajorTeganRuntime()

    return {
        "runtime_engine": runtime_engine,
        "tegan_runtime": tegan_runtime,
    }


def build_runtime_status():

    try:
        captains = get_active_captains()
    except Exception:
        captains = []

    return {
        "status": "online",
        "phase": "runtime_restored",
        "runtime_engine": "active",
        "tegan_runtime": "active",
        "captain_count": len(captains),
        "memory": memory_orchestration_status(),
    }


async def handle_chat(req):

    message = getattr(req, "message", "")

    runtime = RuntimeEngine()

    try:

        result = runtime.process({
            "message": message,
            "source": "api",
            "runtime": "tegan_runtime"
        })

        if isinstance(result, dict):
            return result

        return {
            "reply": str(result),
            "runtime": "tegan_runtime",
            "status": "online"
        }

    except Exception as e:

        return {
            "reply": f"Runtime cognition error: {str(e)}",
            "runtime": "tegan_runtime",
            "status": "degraded"
        }