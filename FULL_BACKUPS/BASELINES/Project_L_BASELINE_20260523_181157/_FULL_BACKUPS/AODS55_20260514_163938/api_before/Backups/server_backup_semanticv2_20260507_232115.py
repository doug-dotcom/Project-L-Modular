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
import json

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

    # =====================================================
    # STORY MEMORY SEARCH
    # =====================================================

    story_matches = search_life_story(user_msg)

    story_context = ""

    if len(story_matches) > 0:

        for item in story_matches:

            story_context += (
                "\n\nSTORY MEMORY:\n" +
                item.get("content","")[:3000]
            )

    system_prompt += story_context

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

LIFE_STORY_FILE = "memory/life_story.json"


os.makedirs(UPLOAD_DIR, exist_ok=True)



def search_life_story(query):

    try:

        if not os.path.exists(LIFE_STORY_FILE):
            return []

        with open(
            LIFE_STORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        matches = []

        query_lower = query.lower()

        for item in data:

            text_blob = (
                str(item.get("title","")) + " " +
                str(item.get("content",""))
            ).lower()

            if query_lower in text_blob:

                matches.append(item)

        return matches[:5]

    except Exception as e:

        print("SEARCH ERROR:", e)

        return []

def save_to_life_story(title, content_text):

    try:

        if os.path.exists(LIFE_STORY_FILE):

            with open(
                LIFE_STORY_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

        else:

            data = []

        entry = {
            "title": title,
            "content": content_text
        }

        data.append(entry)

        with open(
            LIFE_STORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("LIFE STORY SAVE ERROR:", e)


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

            save_to_life_story(
                file.filename,
                vision_text
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







# =========================================================
# LIFE STORY SEARCH
# =========================================================

@app.post("/recall")
async def recall_story(req: ChatRequest):

    query = req.message

    matches = search_life_story(query)

    if len(matches) == 0:

        return {
            "reply":"I could not find anything in your story memory about that yet."
        }

    summary = ""

    for i, item in enumerate(matches):

        summary += f"\n\n--- MEMORY {i+1} ---\n"

        summary += (
            item.get("content","")[:2000]
        )

    return {
        "reply": summary
    }

