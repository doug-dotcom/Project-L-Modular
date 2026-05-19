from core.memory_retriever import retrieve_memory_context

tests = [
    "What sport do I play?",
    "Who are my children?",
    "Tell me about my recovery",
    "What does G know about my masks?",
    "What are my emotional patterns?"
]

for t in tests:

    print("=" * 70)
    print("QUERY:", t)

    result = retrieve_memory_context(t, limit=8)

    print("DOMAINS:", result["domains"])
    print("MEMORIES FOUND:", len(result["memories"]))
    print(result["context"])
    print()
