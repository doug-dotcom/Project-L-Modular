# ============================================================
# DYNAMIC RUNTIME DISPATCH ENGINE
# Major Tegan Dynamic Troop Deployment
# ============================================================

from orchestration.active_registry import (
    get_active_captains
)


def dynamic_dispatch(user_msg):

    captains = get_active_captains()

    deployment_log = []

    for captain in captains:

        try:

            should_handle = captain.should_handle(
                user_msg
            )

            deployment_log.append({
                "captain": captain.name,
                "should_handle": should_handle
            })

            if should_handle:

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
        "captain": None,
        "result": None,
        "deployment_log": deployment_log
    }


def build_dispatch_report(user_msg):

    result = dynamic_dispatch(
        user_msg
    )

    lines = []

    lines.append(
        "MAJOR TEGAN DYNAMIC DISPATCH REPORT"
    )

    lines.append("")

    lines.append(
        f"Handled: {result['handled']}"
    )

    lines.append(
        f"Captain: {result['captain']}"
    )

    lines.append("")

    lines.append("DEPLOYMENT LOG")

    for item in result["deployment_log"]:

        if "error" in item:

            lines.append(
                f"- {item['captain']} ERROR: {item['error']}"
            )

        else:

            lines.append(
                f"- {item['captain']} "
                f"should_handle="
                f"{item['should_handle']}"
            )

    return "\n".join(lines)
