# ============================================================
# EXECUTION COMMAND
# Captain Addie / Captain Tania
# ============================================================

from orchestration.invisible_orchestra import (
    log_orchestra_event,
    compose_l_response,
)

from orchestration.specialist_state import (
    specialist_should_route,
    specialist_complete,
)


def try_execution_command(

    user_msg,

    ADDIE_AVAILABLE,
    addie_should_handle,
    addie_handle_task_request,

    TANIA_AVAILABLE,
    tania_should_handle,
    handle_task_request,

    save_conversation_turn,
    store_handoffs
):

    # =====================================================
    # ADDIE EXECUTION
    # =====================================================

    if (
        ADDIE_AVAILABLE
        and addie_should_handle(user_msg)
    ):

        print("\n✅ ROUTING TO ADDIE")

        addie_result = addie_handle_task_request(
            user_msg
        )

        handoff = addie_result.get(
            "handoff",
            {}
        )

        store_handoffs(
            [],
            [handoff]
        )

        addie_reply = (
            "# ✅ Addie Task Review\n\n"
            "Task cognition active.\n\n"
            "Automatic execution is currently disabled for safety.\n\n"
            "Addie identified a task and is awaiting approval/execution layer completion."
        )

        save_conversation_turn(
            user_msg,
            "✅ Addie + Tania:\n\n"
            + addie_reply
        )

        log_orchestra_event(
            "Addie",
            user_msg,
            addie_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Addie",
            addie_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Addie")

        return {
            "reply": final_reply
        }

    # =====================================================
    # TANIA TASKS
    # =====================================================

    if (
        TANIA_AVAILABLE
        and tania_should_handle(user_msg)
        and specialist_should_route(
            user_msg,
            "Tania"
        )
    ):

        print("\n✅ ROUTING TO TANIA")

        tania_reply = (
            handle_task_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "✅ Tania Tasks:\n\n"
            + tania_reply
        )

        log_orchestra_event(
            "Tania",
            user_msg,
            tania_reply
        )

        final_reply = compose_l_response(
            user_msg,
            "Tania",
            tania_reply
        )

        save_conversation_turn(
            user_msg,
            final_reply
        )

        specialist_complete("Tania")

        return {
            "reply": final_reply
        }

    return None
