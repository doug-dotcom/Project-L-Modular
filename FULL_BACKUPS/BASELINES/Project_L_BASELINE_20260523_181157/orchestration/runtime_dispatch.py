
from orchestration.lieutenants.suppression_lieutenant import (
    SUPPRESSION_LIEUTENANT,
)
# ============================================================
# DYNAMIC RUNTIME DISPATCH ENGINE
# Major Tegan Dynamic Troop Deployment
# ============================================================

from orchestration.active_registry import (
    get_active_captains
)

from orchestration.lieutenants.routing_lieutenant import (
    ROUTING_LIEUTENANT,
)


def dynamic_dispatch(user_msg):

    captains = get_active_captains()

    deployment_log = []

    routing = (
        ROUTING_LIEUTENANT
        .select_best_captain(
            captains,
            user_msg
        )
    )

    best = routing.get("best")

    deployment_log.extend(
        routing.get("all_scores", [])
    )

    if not best:

        return {
            "handled": False,
            "captain": None,
            "result": None,
            "deployment_log": deployment_log
        }

    captain = best.get("captain")

    if not captain:

        return {
            "handled": False,
            "captain": None,
            "result": None,
            "deployment_log": deployment_log
        }

    try:

        result = captain.execute(
            user_msg
        )

        return {
            "handled": True,
            "captain": captain.name,
            "result": result,
            "deployment_log": deployment_log
        }

    except Exception as e:

        deployment_log.append({
            "captain": captain.name,
            "error": str(e)
        })

        return {
            "handled": False,
            "captain": captain.name,
            "result": None,
            "deployment_log": deployment_log
        }

