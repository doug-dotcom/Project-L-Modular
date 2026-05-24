from services.runtime_completion_seal_service import (
    create_completion_seal,
    completion_seal_status,
    completion_summary,
    operator_completion_brief
)

print("")
print("===================================")
print("AODS 90 VALIDATION")
print("===================================")
print("")

print("CREATE COMPLETION SEAL:")
print(create_completion_seal())

print("")
print("SEAL STATUS:")
print(completion_seal_status())

print("")
print("COMPLETION SUMMARY:")
print(completion_summary())

print("")
print("OPERATOR COMPLETION BRIEF:")
print(operator_completion_brief())
