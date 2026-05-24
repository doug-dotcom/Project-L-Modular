from services.runtime_intent_service import (
    intent_patterns,
    detect_intents,
    dominant_intent,
    intent_summary,
    intent_status
)

print("")
print("===================================")
print("AODS 79 VALIDATION")
print("===================================")
print("")

print("INTENT STATUS:")
print(intent_status())

print("")
print("INTENT PATTERNS:")
print(intent_patterns())

test_input = """
AODS runtime drift is increasing and
we need to slow expansion and stabilise
the architecture before deploying more.
"""

print("")
print("DETECTED INTENTS:")
print(detect_intents(test_input))

print("")
print("DOMINANT INTENT:")
print(dominant_intent(test_input))

print("")
print("INTENT SUMMARY:")
print(intent_summary(test_input))
