from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import TIMEZONE


def get_current_time():

    return datetime.now(
        ZoneInfo(TIMEZONE)
    )


def build_time_context():

    current_time = get_current_time()

    return f\"\"\"

CURRENT DATE/TIME:
{current_time.strftime("%A %d %B %Y")}
{current_time.strftime("%I:%M %p")}

Timezone:
{TIMEZONE}

\"\"\"
