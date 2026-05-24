from services.runtime_governance_service import (
    governance_status,
    constitutional_alignment,
    governance_recommendation,
    governance_brief
)

print("")
print("===================================")
print("AODS 74 VALIDATION")
print("===================================")
print("")

print("GOVERNANCE STATUS:")
print(governance_status())

print("")
print("CONSTITUTIONAL ALIGNMENT:")
print(constitutional_alignment())

print("")
print("GOVERNANCE RECOMMENDATION:")
print(governance_recommendation())

print("")
print("GOVERNANCE BRIEF:")
print(governance_brief())
