# ============================================================
# SHINE L RUNTIME ENGINE
# Distributed Cognition Pipeline
# ============================================================

from orchestration.tegan_runtime import (
    MajorTeganRuntime
)

from memory.local_runtime import (
    process,
    build_context
)

from core.emotional_confidence import (
    calculate_emotional_confidence,
    build_calm_cognition_layer
)

from core.conversational_maturity import (
    apply_conversational_maturity
)

from core.response_stabilizer import (
    stabilize_response,
    apply_final_stabilization
)

from core.prompt_builder import (
    build_system_prompt
)

from orchestration.weighted_scoring import (
    score_cognition_domains,
    calculate_agent_confidence,
    orchestration_summary,
    build_orchestra_context
)

from memory.confidence import (
    apply_memory_confidence
)


class RuntimeEngine:

    def __init__(self):

        self.tegan = (
            MajorTeganRuntime()
        )

    # ========================================================
    # PROCESS MESSAGE
    # ========================================================

    def process_message(
        self,
        user_msg,
        runtime_context
    ):

        # ================================================
        # MEMORY PROCESS
        # ================================================

        process(user_msg)

        memory_context = build_context()

        # ================================================
        # EMOTIONAL
        # ================================================

        emotional_confidence = (
            calculate_emotional_confidence(
                user_msg
            )
        )

        calm_layer = (
            build_calm_cognition_layer(
                emotional_confidence
            )
        )

        # ================================================
        # COGNITION
        # ================================================

        cognition_scores = (
            score_cognition_domains(
                user_msg
            )
        )

        cognition_context = (
            build_orchestra_context(
                cognition_scores
            )
        )

        weighted_agents = (
            calculate_agent_confidence(
                user_msg
            )
        )

        cognition_context += (
            orchestration_summary(
                weighted_agents
            )
        )

        # ================================================
        # PROMPT
        # ================================================

        system_prompt = (
            build_system_prompt(
                time_context=runtime_context.get(
                    "time_context",
                    ""
                ),

                memory_context=memory_context,

                tone=runtime_context.get(
                    "tone",
                    ""
                ),

                cognition_context=cognition_context,

                calm_cognition_context=calm_layer,

                active_skill_layer=runtime_context.get(
                    "active_skill_layer",
                    ""
                )
            )
        )

        # ================================================
        # TEGAN DEPLOYMENT
        # ================================================

        deployment = (
            self.tegan.process(
                user_msg
            )
        )

        return {

            "system_prompt": system_prompt,

            "deployment": deployment,

            "memory_context": memory_context,

            "cognition_context": cognition_context
        }

    # ========================================================
    # FINALIZE RESPONSE
    # ========================================================

    def finalize_response(
        self,
        reply,
        user_msg
    ):

        reply = stabilize_response(
            reply
        )

        reply = apply_memory_confidence(
            reply,
            user_msg
        )

        reply = apply_conversational_maturity(
            reply,
            user_msg
        )

        reply = apply_final_stabilization(
            reply
        )

        return reply
