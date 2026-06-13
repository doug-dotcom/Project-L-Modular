from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import UploadFile, File
import shutil
import os
import fitz
import base64

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




# =========================================================
# FILE UPLOAD ENDPOINT
# =========================================================

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_text = ""

    # PDF SUPPORT
    if file.filename.lower().endswith(".pdf"):

        try:

            doc = fitz.open(file_path)

            for page in doc:
                file_text += page.get_text()

            doc.close()

        except Exception as e:

            return {
                "status": "error",
                "message": f"PDF read failed: {str(e)}"
            }

    # TXT SUPPORT
    elif file.filename.lower().endswith(".txt"):

        try:

            with open(file_path, "r", encoding="utf-8") as f:
                file_text = f.read()

        except Exception as e:

            return {
                "status": "error",
                "message": f"TXT read failed: {str(e)}"
            }

    # IMAGE SUPPORT
    elif (
        file.filename.lower().endswith(".png")
        or file.filename.lower().endswith(".jpg")
        or file.filename.lower().endswith(".jpeg")
    ):

        try:

            with open(file_path, "rb") as img_file:

                base64_image = base64.b64encode(
                    img_file.read()
                ).decode("utf-8")

            vision_response = client.chat.completions.create(

                model="gpt-4o-mini",

                messages=[

                    {
                        "role":"user",
                        "content":[
                            {
                                "type":"text",
                                "text":"Analyze this image and describe it clearly."
                            },
                            {
                                "type":"image_url",
                                "image_url":{
                                    "url":f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            )

            vision_text = (
                vision_response
                .choices[0]
                .message
                .content
            )

            process(
                f"User uploaded image: {file.filename}"
            )

            return {
                "status":"success",
                "filename":file.filename,
                "preview":vision_text
            }

        except Exception as e:

            return {
                "status":"error",
                "message":f"Image analysis failed: {str(e)}"
            }

    else:

        return {
            "status": "uploaded",
            "filename": file.filename,
            "message": "File uploaded successfully."
        }

    process(f"User uploaded file: {file.filename}")

    return {
        "status": "success",
        "filename": file.filename,
        "preview": file_text[:3000]
    }


