from orchestration.routing.engine import (
    route_request
)

tests = [

    "Check my email",

    "Schedule an appointment",

    "Help me with memory continuity",

    "I feel stressed and overwhelmed",

    "Explain the meaning of this insight"
]

for test in tests:

    print()
    print("INPUT:", test)

    print(
        route_request(test)
    )

