META_SUPPRESSION_TERMS = [

    "orchestration",
    "routing",
    "agent",
    "agents",
    "system design",
    "architecture",
    "memory audit",
    "memory observability",
    "trigger logic",
    "suppression logic",
    "weighted routing",
    "cognition",
    "hard fix",
    "soft fix",
    "backend",
    "frontend",
    "server.py",
    "routes",
    "engines",
    "api"

]


def suppress_agent_routing(message):

    text = message.lower()

    for term in META_SUPPRESSION_TERMS:

        if term in text:

            print("")
            print("🛑 META ROUTING SUPPRESSION ACTIVE")
            print("TERM:", term)

            return True

    return False
