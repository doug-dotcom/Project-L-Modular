from services.runtime_lock_service import (
    runtime_lock_status,
    runtime_lock_rules,
    evaluate_lock_conditions,
    apply_runtime_lock,
    lock_brief,
    runtime_permitted
)

print("")
print("===================================")
print("AODS 82 VALIDATION")
print("===================================")
print("")

print("LOCK STATUS:")
print(runtime_lock_status())

print("")
print("LOCK RULES:")
print(runtime_lock_rules())

print("")
print("LOCK EVALUATION:")
print(evaluate_lock_conditions())

print("")
print("APPLY LOCK:")
print(apply_runtime_lock())

print("")
print("LOCK BRIEF:")
print(lock_brief())

print("")
print("RUNTIME PERMITTED:")
print(runtime_permitted())
