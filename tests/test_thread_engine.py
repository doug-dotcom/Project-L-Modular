from services.chat_service import generate_reply
from services.thread_debug_service import debug_thread

print("")
print("===================================")
print("AODS 55 VALIDATION")
print("===================================")
print("")

thread_id = "demo"

print("Generating replies...")
print("")

r1 = generate_reply(
    "Hello L this is the start of a persistent thread",
    thread_id=thread_id
)

r2 = generate_reply(
    "Can you remember what I just said?",
    thread_id=thread_id
)

print("REPLY 1:")
print(r1)

print("")
print("REPLY 2:")
print(r2)

print("")
print("THREAD DEBUG:")
print(debug_thread(thread_id))
