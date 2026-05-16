# ============================================================
# RESEARCH + FINANCE COMMAND
# Captain Noelie / Captain Fiona / Captain Brittany
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


def try_research_finance_command(

    user_msg,

    FIONA_AVAILABLE,
    fiona_should_handle,
    handle_finance_request,

    NOELIE_AVAILABLE,
    noelie_should_handle,
    handle_research_request,

    BRITTANY_AVAILABLE,
    brittany_should_handle,
    brittany_investigate,

    save_conversation_turn
):

    # =====================================================
    # FIONA FINANCE
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and FIONA_AVAILABLE
        and fiona_should_handle(user_msg)
    ):

        print("\n💰 ROUTING TO FIONA")

        fiona_reply = handle_finance_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "💰 Fiona Finance:\n\n"
            + fiona_reply
        )

        log_orchestra_event(
            "Fiona",
            user_msg,
            fiona_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Fiona",
            fiona_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Fiona")

        return {
            "reply": final_reply
        }

    # =====================================================
    # NOELIE RESEARCH
    # =====================================================

    if (
        not suppress_agent_routing(user_msg)
        and NOELIE_AVAILABLE
        and noelie_should_handle(user_msg)
    ):

        print("\n🌐 ROUTING TO NOELIE")

        noelie_reply = handle_research_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🌐 Noelie Knowledge Research:\n\n"
            + noelie_reply
        )

        log_orchestra_event(
            "Noelie",
            user_msg,
            noelie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Noelie",
            noelie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Noelie")

        return {
            "reply": final_reply
        }

    # =====================================================
    # BRITTANY BROWSER
    # =====================================================

    if (
        BRITTANY_AVAILABLE
        and brittany_should_handle(user_msg)
    ):

        print("\n🌐 ROUTING TO BRITTANY")

        brittany_reply = brittany_investigate(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🌐 Brittany Browser:\n\n"
            + brittany_reply
        )

        log_orchestra_event(
            "Brittany",
            user_msg,
            brittany_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Brittany",
            brittany_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Brittany")

        return {
            "reply": final_reply
        }

    return None
