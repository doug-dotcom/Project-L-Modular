from services.runtime_learning_service import (
    record_successful_pattern,
    record_failed_pattern,
    learning_summary,
    adaptive_recommendation,
    recent_learning
)

print("")
print("===================================")
print("AODS 76 VALIDATION")
print("===================================")
print("")

print("RECORD SUCCESS:")

print(
    record_successful_pattern(
        pattern="slow_modular_expansion",
        context={
            "result": "stable_runtime"
        }
    )
)

print("")
print("RECORD FAILURE:")

print(
    record_failed_pattern(
        pattern="unsafe_regex_patch",
        context={
            "result": "parser_failure"
        }
    )
)

print("")
print("LEARNING SUMMARY:")
print(learning_summary())

print("")
print("ADAPTIVE RECOMMENDATION:")
print(adaptive_recommendation())

print("")
print("RECENT LEARNING:")
print(recent_learning())
