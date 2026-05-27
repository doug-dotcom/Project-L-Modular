# ============================================================
# VISUAL OPERATIONS COMMAND
# Captain Pixie
# ============================================================

from orchestration.invisible_orchestra import (
    log_orchestra_event,
    compose_l_response,
)


def try_visual_command(
    user_msg,

    PIXIE_AVAILABLE,
    pixie_should_handle,
    pixie_create_image,

    save_conversation_turn
):

    if (
        PIXIE_AVAILABLE
        and pixie_should_handle(user_msg)
    ):

        print("\n🎨 ROUTING TO PIXIE")

        try:

            result = pixie_create_image(
                user_msg
            )

            if not result:

                return {
                    "reply": "❌ Pixie returned no image result."
                }

            pixie_reply = result.get(
                "reply",
                "Pixie created an image."
            )

            log_orchestra_event(
                "Pixie",
                user_msg,
                pixie_reply
            )

            final_reply = compose_l_response(
                user_msg,
                "Pixie",
                pixie_reply
            )

            save_conversation_turn(
                user_msg,
                final_reply
            )

            return {
                "reply": final_reply,
                "image_url": result.get(
                    "image_url",
                    ""
                )
            }

        except Exception as e:

            print(
                "PIXIE GENERATION ERROR:",
                e
            )

            return {
                "reply":
                    "❌ Pixie generation failed:\n\n"
                    + str(e)
            }

    return None

