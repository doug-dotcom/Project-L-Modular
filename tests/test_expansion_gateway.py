from services.runtime_expansion_gateway_service import (
    expansion_policy,
    expansion_readiness,
    expansion_gate,
    expansion_brief
)

print("")
print("===================================")
print("AODS 75 VALIDATION")
print("===================================")
print("")

print("EXPANSION POLICY:")
print(expansion_policy())

print("")
print("EXPANSION READINESS:")
print(expansion_readiness())

print("")
print("MINOR PATCH GATE:")
print(expansion_gate("minor_patch"))

print("")
print("RUNTIME FEATURE GATE:")
print(expansion_gate("runtime_feature"))

print("")
print("ARCHITECTURE SHIFT GATE:")
print(expansion_gate("architecture_shift"))

print("")
print("EXPANSION BRIEF:")
print(expansion_brief())
