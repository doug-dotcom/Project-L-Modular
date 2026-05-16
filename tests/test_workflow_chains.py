from services.workflow_chain_service import (
    execute_chain,
    category_to_chain,
    get_chain
)

print("")
print("===================================")
print("AODS 58 VALIDATION")
print("===================================")
print("")

categories = [
    "memory",
    "care",
    "build",
    "email",
    "calendar",
    "general"
]

for c in categories:

    print("CATEGORY:", c)
    print("CHAIN NAME:", category_to_chain(c))
    print("CHAIN STEPS:", get_chain(category_to_chain(c)))

    result = execute_chain(
        c,
        {
            "message": "validation",
            "thread_id": "aods58"
        }
    )

    print("RESULT:")
    print(result)

    print("")
    print("===================================")
    print("")
