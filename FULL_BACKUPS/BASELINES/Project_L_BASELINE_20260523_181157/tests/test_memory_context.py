from services.memory_context_service import build_memory_context
from services.memory_debug_service import debug_memory_context

print("")
print("===================================")
print("AODS 54 VALIDATION")
print("===================================")
print("")

context = build_memory_context()

print("MEMORY CONTEXT:")
print(context)

print("")
print("DEBUG SNAPSHOT:")
print(debug_memory_context())
