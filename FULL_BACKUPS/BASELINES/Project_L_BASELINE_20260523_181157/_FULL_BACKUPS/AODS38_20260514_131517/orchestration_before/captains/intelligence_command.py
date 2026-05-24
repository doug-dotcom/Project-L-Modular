# ============================================================
# INTELLIGENCE COMMAND
# Captain Millie / Captain Richie / Captain Gracie
# ============================================================

from orchestration.invisible_orchestra import (
    log_orchestra_event,
    compose_l_response,
)

from orchestration.meta_suppression import (
    suppress_agent_routing,
)

from orchestration.specialist_state import (
    specialist_complete,
)


def try_intelligence_command(

    user_msg,

    MILLIE_AVAILABLE,
    millie_should_handle,
    handle_memory_request,

    RICHIE_AVAILABLE,
    richie_should_handle,
    handle_reflection_request,

    GRACIE_AVAILABLE,
    gracie_should_handle,
    handle_legacy_request,

    save_conversation_turn
):

    # =====================================================
    # RICHIE REFLECTION
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and RICHIE_AVAILABLE
        and richie_should_handle(user_msg)
    ):

        print("\n🪞 ROUTING TO RICHIE")

        richie_reply = handle_reflection_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🪞 Richie Reflective Learning:\n\n"
            + richie_reply
        )

        log_orchestra_event(
            "Richie",
            user_msg,
            richie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Richie",
            richie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Richie")

        return {
            "reply": final_reply
        }

    # =====================================================
    # GRACIE LEGACY
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and GRACIE_AVAILABLE
        and gracie_should_handle(user_msg)
    ):

        print("\n📖 ROUTING TO GRACIE")

        gracie_reply = handle_legacy_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "📖 Gracie Legacy Builder:\n\n"
            + gracie_reply
        )

        log_orchestra_event(
            "Gracie",
            user_msg,
            gracie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Gracie",
            gracie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Gracie")

        return {
            "reply": final_reply
        }

    # =====================================================
    # MILLIE MEMORY
    # =====================================================

    if (
        MILLIE_AVAILABLE
        and millie_should_handle(user_msg)
    ):

        print("\n🧠 ROUTING TO MILLIE")

        millie_reply = handle_memory_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🧠 Millie Memory Keeper:\n\n"
            + millie_reply
        )

        log_orchestra_event(
            "Millie",
            user_msg,
            millie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Millie",
            millie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Millie")

        return {
            "reply": final_reply
        }

    return None
