from services.runtime_semantic_index_service import (
    semantic_index,
    semantic_search,
    semantic_status,
    recent_index_items,
    semantic_summary
)

print("")
print("===================================")
print("AODS 78 VALIDATION")
print("===================================")
print("")

print("SEMANTIC STATUS:")
print(semantic_status())

print("")
print("INDEX ITEMS:")

semantic_index(
    label="drift_control",
    text="""
    Runtime drift reduced by slowing expansion
    and validating modular architecture carefully.
    """,
    source_type="learning"
)

semantic_index(
    label="guardian_runtime",
    text="""
    Guardian loop monitors alignment,
    confidence and runtime stability.
    """,
    source_type="guardian"
)

print("")
print("UPDATED STATUS:")
print(semantic_status())

print("")
print("SEMANTIC SEARCH:")
print(
    semantic_search(
        "runtime drift stability"
    )
)

print("")
print("RECENT INDEX ITEMS:")
print(recent_index_items())

print("")
print("SEMANTIC SUMMARY:")
print(semantic_summary())
