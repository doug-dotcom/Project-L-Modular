from agents.brittany_browser import brittany
from agents.emily import emily
from agents.callie import callie
from agents.tanya import tanya
from agents.fiona import fiona

def route_message(message: str):

    try:

        if emily.should_handle(message):

            return {

                "handled": True,
                "agent": "Emily",
                "reply":
                    emily.handle_email_request(message)

            }

    except Exception as e:

        return {

            "handled": True,
            "agent": "Emily",
            "reply":
                f"Emily Error: {str(e)}"

        }

    try:

        if callie.should_handle(message):

            return {

                "handled": True,
                "agent": "Callie",
                "reply":
                    callie.handle_calendar_request(message)

            }

    except Exception as e:

        return {

            "handled": True,
            "agent": "Callie",
            "reply":
                f"Callie Error: {str(e)}"

        }

    try:

        if tanya.should_handle(message):

            return {

                "handled": True,
                "agent": "Tanya",
                "reply":
                    tanya.handle_task_request(message)

            }

    except Exception as e:

        return {

            "handled": True,
            "agent": "Tanya",
            "reply":
                f"Tanya Error: {str(e)}"

        }


    try:

        if fiona.should_handle(message):

            return {

                "handled": True,
                "agent": "Fiona",
                "reply":
                    fiona.handle_finance_request(message)

            }

    except Exception as e:

        return {

            "handled": True,
            "agent": "Fiona",
            "reply":
                f"Fiona Error: {str(e)}"

        }

    try:

        if brittany.should_handle(message):

            return {

                "handled": True,
                "agent": "Brittany",
                "reply":
                    brittany.investigate(message)

            }

    except Exception as e:

        return {

            "handled": True,
            "agent": "Brittany",
            "reply":
                f"Brittany Error: {str(e)}"

        }

    return {

        "handled": False,
        "agent": "L Core",
        "reply": ""

    }

