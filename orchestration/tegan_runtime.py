from orchestration.lieutenants.observability_lieutenant import (
    OBSERVABILITY_LIEUTENANT,
)
from orchestration.lieutenants.continuity_lieutenant import (
    CONTINUITY_LIEUTENANT,
)
# ============================================================
# MAJOR TEGAN RUNTIME CONTROLLER
# Operational Command Layer
# ============================================================

from orchestration.tegan_triage import (
    assess_urgency
)

from orchestration.meta_suppression import (
    suppress_agent_routing
)

from orchestration.runtime_dispatch import (
    dynamic_dispatch
)


class MajorTeganRuntime:

    def __init__(self):

        self.name = "Major Tegan Triage"

        self.rank = "Major"

    # ========================================================
    # PROCESS
    # ========================================================

    def process(
        self,
        user_msg
    ):

        urgency = assess_urgency(
            user_msg
        )

        suppression = suppress_agent_routing(
            user_msg
        )

        deployment = dynamic_dispatch(
            user_msg
        )

        
        CONTINUITY_LIEUTENANT.update_context(
            user_msg,
            deployment
        )

        continuity_layer = (
            CONTINUITY_LIEUTENANT
            .build_continuity_layer()
        )

        
        OBSERVABILITY_LIEUTENANT.record_event(
            "runtime_process",
            {
                "captain": deployment.get(
                    "captain"
                ),
                "handled": deployment.get(
                    "handled"
                ),
                "message": user_msg[:200]
            }
        )

        return {

            "runtime_controller": self.name,

            "urgency": urgency,

            "suppression": suppression,

            "deployment": deployment,

            "continuity_layer": continuity_layer
        }

    # ========================================================
    # REPORT
    # ========================================================

    def build_runtime_report(
        self,
        user_msg
    ):

        result = self.process(
            user_msg
        )

        deployment = result[
            "deployment"
        ]

        lines = []

        lines.append(
            "MAJOR TEGAN RUNTIME REPORT"
        )

        lines.append("")

        lines.append(
            f"Urgency: "
            f"{result['urgency']}"
        )

        lines.append(
            f"Suppression: "
            f"{result['suppression']}"
        )

        lines.append("")

        lines.append(
            f"Handled: "
            f"{deployment['handled']}"
        )

        lines.append(
            f"Captain: "
            f"{deployment['captain']}"
        )

        lines.append("")

        lines.append(
            "DEPLOYMENT LOG"
        )

        for item in deployment[
            "deployment_log"
        ]:

            if "error" in item:

                lines.append(
                    f"- {item['captain']} "
                    f"ERROR: "
                    f"{item['error']}"
                )

            else:

                lines.append(
                    f"- {item['captain']} "
                    f"should_handle="
                    f"{item['should_handle']}"
                )

        return "\n".join(lines)


