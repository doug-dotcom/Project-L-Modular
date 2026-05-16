from services.action_execution_service import execute_user_request

print("")
print("===================================")
print("AODS 57 VALIDATION")
print("===================================")
print("")

tests = [
    "remember this conversation for later",
    "send an email to Lyndal",
    "book a calendar meeting",
    "I feel overwhelmed and anxious",
    "AODS build runtime deploy",
    "hello L"
]

for t in tests:

    print("INPUT:")
    print(t)
    print("")

    result = execute_user_request(
        t,
        thread_id="aods57"
    )

    print("RESULT:")
    print(result)
    print("")
    print("===================================")
    print("")
