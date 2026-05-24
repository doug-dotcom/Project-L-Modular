from services.orchestration_service import ORCHESTRATOR
from services.memory_service import runtime_memory_status

print("ORCHESTRATOR:")
print(ORCHESTRATOR.heartbeat())

print("")
print("MEMORY STATUS:")
print(runtime_memory_status())
