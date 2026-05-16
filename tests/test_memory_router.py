from core.memory_router import save_memory, memory_summary

save_memory("scratchpad", {
    "event": "AODS49_TEST",
    "status": "PASS"
})

print(memory_summary())
