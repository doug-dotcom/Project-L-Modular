# ============================================================
# SHINE L - CAPTAIN REGISTRY
# MAJOR TEGAN TRIAGE OPERATIONAL ROSTER
# ============================================================


CAPTAIN_REGISTRY = {

    "Emily": {
        "rank": "Captain",
        "domain": "communications",
        "specialty": "email cognition",
        "visibility": "human-facing",
        "active": True
    },

    "Callie": {
        "rank": "Captain",
        "domain": "calendar",
        "specialty": "scheduling operations",
        "visibility": "human-facing",
        "active": True
    },

    "Millie": {
        "rank": "Captain",
        "domain": "memory",
        "specialty": "memory continuity",
        "visibility": "human-facing",
        "active": True
    },

    "Fiona": {
        "rank": "Captain",
        "domain": "finance",
        "specialty": "financial cognition",
        "visibility": "human-facing",
        "active": True
    },

    "Emme": {
        "rank": "Captain",
        "domain": "emotional regulation",
        "specialty": "nervous system support",
        "visibility": "human-facing",
        "active": True
    },

    "Richie": {
        "rank": "Captain",
        "domain": "reflection",
        "specialty": "reflective learning",
        "visibility": "human-facing",
        "active": True
    },

    "Gracie": {
        "rank": "Captain",
        "domain": "legacy",
        "specialty": "legacy preservation",
        "visibility": "human-facing",
        "active": True
    },

    "Noelie": {
        "rank": "Captain",
        "domain": "research",
        "specialty": "knowledge investigation",
        "visibility": "human-facing",
        "active": True
    },

    "Brittany": {
        "rank": "Captain",
        "domain": "browser research",
        "specialty": "web investigation",
        "visibility": "human-facing",
        "active": True
    },

    "Addie": {
        "rank": "Captain",
        "domain": "execution",
        "specialty": "task execution",
        "visibility": "human-facing",
        "active": True
    },

    "Tania": {
        "rank": "Captain",
        "domain": "tasks",
        "specialty": "task management",
        "visibility": "human-facing",
        "active": True
    },

    "Pixie": {
        "rank": "Captain",
        "domain": "visual operations",
        "specialty": "image generation",
        "visibility": "human-facing",
        "active": True
    },

    "Winnie": {
        "rank": "Captain",
        "domain": "whatsapp cognition",
        "specialty": "messaging continuity",
        "visibility": "human-facing",
        "active": True
    }

}


def get_captain(name):

    return CAPTAIN_REGISTRY.get(name)


def get_active_captains():

    return {

        name: info

        for name, info in CAPTAIN_REGISTRY.items()

        if info.get("active")
    }


def get_captain_domains():

    return {

        name: info.get("domain")

        for name, info in CAPTAIN_REGISTRY.items()
    }


def get_captain_specialties():

    return {

        name: info.get("specialty")

        for name, info in CAPTAIN_REGISTRY.items()
    }


def build_captain_status_report():

    lines = []

    lines.append("SHINE L CAPTAIN REGISTRY")
    lines.append("")

    for name, info in CAPTAIN_REGISTRY.items():

        lines.append(
            f"{name} | "
            f"{info.get('rank')} | "
            f"{info.get('domain')} | "
            f"{info.get('specialty')}"
        )

    return "\n".join(lines)
