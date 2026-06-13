from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

# 👉 Ellie (memory brain)
from memory.memory_engine import process, build_context, detect_emotional_state, generate_emotional_tone

# 🔥 CONFIRM CORRECT FILE IS RUNNING
print("🚀 USING CORRECT SERVER.PY")

app = FastAPI()

# -------------------------
# CORS (UI FIX)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://shine-l.netlify.app"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI()

# -------------------------
# REQUEST MODEL
# -------------------------
class ChatRequest(BaseModel):
    message: str

# -------------------------
# CHAT ENDPOINT
# -------------------------
@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = req.message

    print("\n🟡 USER MESSAGE:", user_msg)

    # 🧠 STEP 1 — store memory
    process(user_msg)

    # 🧠 STEP 2 — build memory context
    memory_context = build_context()
    state = detect_emotional_state(user_msg)
    tone = generate_emotional_tone(state)

    print("\n🧠 MEMORY CONTEXT:\n", memory_context)

    system_prompt = f"""
You are L, a personal assistant with persistent memory.

Here is everything you know about the user:

{memory_context}

Tone instruction:
{tone}

Instructions:
- ALWAYS use the memory above when answering
- If the answer is clearly in memory, answer confidently
- Do NOT say you don't know if it exists in memory
- Be calm, direct, and helpful
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ]
    )

    reply = response.choices[0].message.content

    print("\n🟢 L RESPONSE:", reply)

    return {"reply": reply}

# -------------------------
# HEALTH CHECK
# -------------------------
@app.get("/")
def root():
    return {
        "status": "L SERVER RUNNING",
        "memory": "Ellie connected",
        "cors": "enabled"
    }

