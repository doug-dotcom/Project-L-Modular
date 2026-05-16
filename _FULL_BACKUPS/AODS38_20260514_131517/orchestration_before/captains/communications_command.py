# ============================================================
# COMMUNICATIONS COMMAND
# Captain Emily / Captain Callie / Captain Winnie
# ============================================================

from orchestration.invisible_orchestra import (
    log_orchestra_event,
    compose_l_response,
)

from orchestration.specialist_state import (
    specialist_should_route,
    specialist_complete,
)


def try_communications_command(
    user_msg,

    WINNIE_AVAILABLE,
    winnie_should_handle,
    handle_whatsapp_request,

    CALLIE_AVAILABLE,
    callie_should_handle,
    handle_calendar_request,

    EMILY_AVAILABLE,
    emily_should_handle,
    handle_email_request,

    save_conversation_turn
):

    # =====================================================
    # WINNIE WHATSAPP
    # =====================================================

    if (
        WINNIE_AVAILABLE
        and winnie_should_handle(user_msg)
    ):

        print("\n💬 ROUTING TO WINNIE WHATSAPP")

        winnie_reply = handle_whatsapp_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "💬 Winnie WhatsApp:\n\n"
            + winnie_reply
        )

        log_orchestra_event(
            "Winnie",
            user_msg,
            winnie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Winnie",
            winnie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Winnie")

        return {
            "reply": final_reply
        }

    # =====================================================
    # CALLIE CALENDAR
    # =====================================================

    if (
        CALLIE_AVAILABLE
        and callie_should_handle(user_msg)
        and specialist_should_route(
            user_msg,
            "Callie"
        )
    ):

        print("\n📅 ROUTING TO CALLIE")

        callie_reply = (
            handle_calendar_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "📅 Callie Calendar:\n\n"
            + callie_reply
        )

        log_orchestra_event(
            "Callie",
            user_msg,
            callie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Callie",
            callie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Callie")

        return {
            "reply": final_reply
        }

    # =====================================================
    # EMILY EMAIL
    # =====================================================

    if (
        EMILY_AVAILABLE
        and emily_should_handle(user_msg)
        and specialist_should_route(
            user_msg,
            "Emily"
        )
    ):

        print("\n📧 ROUTING TO EMILY EMAIL")

        emily_reply = (
            handle_email_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "📧 Emily Email:\n\n"
            + emily_reply
        )

        log_orchestra_event(
            "Emily",
            user_msg,
            emily_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Emily",
            emily_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Emily")

        return {
            "reply": final_reply
        }

    return None
