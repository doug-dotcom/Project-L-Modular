from memory.behaviour.engine import (
    record_behaviour_from_exchange,
    build_behaviour_patterns,
    truth_implementation_status,
)

print("Testing Behaviour Layer v1...")

result = record_behaviour_from_exchange(
    "G I feel overwhelmed but I want to build Project L properly and not break live L.",
    "That sounds like overload mixed with motivation. We can build safely in stages."
)

print("Recorded:")
print(result)

patterns = build_behaviour_patterns()
print("Patterns:")
print(patterns)

print("Truth status:")
print(truth_implementation_status())
