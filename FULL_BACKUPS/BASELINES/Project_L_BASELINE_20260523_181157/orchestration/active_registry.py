# ============================================================
# ACTIVE CAPTAIN REGISTRY
# Major Tegan Runtime Officer Roster
# ============================================================

from orchestration.captains.communications.captain_emily import (
    CaptainEmily
)

from orchestration.captains.communications.captain_callie import (
    CaptainCallie
)

from orchestration.captains.communications.captain_winnie import (
    CaptainWinnie
)

from orchestration.captains.intelligence.captain_millie import (
    CaptainMillie
)

from orchestration.captains.intelligence.captain_richie import (
    CaptainRichie
)

from orchestration.captains.intelligence.captain_gracie import (
    CaptainGracie
)

from orchestration.captains.research_finance.captain_fiona import (
    CaptainFiona
)

from orchestration.captains.research_finance.captain_noelie import (
    CaptainNoelie
)

from orchestration.captains.research_finance.captain_brittany import (
    CaptainBrittany
)

from orchestration.captains.execution_visual.captain_addie import (
    CaptainAddie
)

from orchestration.captains.execution_visual.captain_tania import (
    CaptainTania
)

from orchestration.captains.execution_visual.captain_pixie import (
    CaptainPixie
)


ACTIVE_CAPTAINS = []


def register_active_captains(captains):

    global ACTIVE_CAPTAINS

    ACTIVE_CAPTAINS = captains


def get_active_captains():

    return ACTIVE_CAPTAINS


def build_runtime_roster():

    lines = []

    lines.append(
        "MAJOR TEGAN ACTIVE RUNTIME ROSTER"
    )

    lines.append("")

    for captain in ACTIVE_CAPTAINS:

        status = captain.status()

        lines.append(
            f"{status['rank']} "
            f"{status['name']} "
            f"({status['domain']})"
        )

    return "\n".join(lines)
