from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
import base64
import fitz

from memory.memory_engine import (
    process,
    build_context,
    detect_emotional_state,
    generate_emotional_tone,
)

load_dotenv()

print("USING CLEAN SHINE L SERVER V2")


# =========================================================
# GOOGLE CLOUD AUTH
# =========================================================
try:
    from api.google_auth import (
        build_auth_url,
        handle_callback,
        google_status,
        clear_credentials
    )

    GOOGLE_AUTH_AVAILABLE = True

except Exception as e:

    print("GOOGLE AUTH IMPORT ERROR:", e)

    GOOGLE_AUTH_AVAILABLE = False


# =========================================================
# PIXIE PICTURES AGENT
# =========================================================
try:

    from agents.pixie.pixie import (
        should_handle as pixie_should_handle
    )

    from agents.pixie.pixie import (
        create_image as pixie_create_image
    )

    PIXIE_AVAILABLE = True

except Exception as e:

    print("PIXIE IMPORT ERROR:", e)

    PIXIE_AVAILABLE = False

app = FastAPI()

# =====================================================
# STATIC IMAGE CORS FIX
# =====================================================

from fastapi.responses import Response

@app.middleware("http")
async def add_cors_headers(request, call_next):

    response = await call_next(request)

    response.headers["Access-Control-Allow-Origin"] = "*"

    response.headers["Access-Control-Allow-Methods"] = "*"

    response.headers["Access-Control-Allow-Headers"] = "*"

    return response

app.add_middleware(HTTPSRedirectMiddleware)
client = OpenAI()

# =========================================================
# GENERATED IMAGE STATIC FILES
# =========================================================

os.makedirs(
    "generated_images",
    exist_ok=True
)

app.mount(
    "/generated_images",
    StaticFiles(directory="generated_images"),
    name="generated_images"
)








# =========================================================
# ADDIE TASK EXECUTION AGENT
# =========================================================
try:

    from agents.addie.addie import (
        should_handle as addie_should_handle
    )

    from agents.addie.addie import (
        handle_task_request as addie_handle_task_request
    )

    ADDIE_AVAILABLE = True

except Exception as e:

    print("ADDIE IMPORT ERROR:", e)

    ADDIE_AVAILABLE = False

# =========================================================
# EMME EMOTIONAL SUPPORT AGENT
# =========================================================
try:

    from agents.emme.emme import (
        should_handle as emme_should_handle
    )

    from agents.emme.emme import (
        handle_emotional_request
    )

    EMME_AVAILABLE = True

except Exception as e:

    print("EMME IMPORT ERROR:", e)

    EMME_AVAILABLE = False

# =========================================================
# MILLIE MEMORY KEEPER AGENT
# =========================================================
try:

    from agents.millie.millie import (
        should_handle as millie_should_handle
    )

    from agents.millie.millie import (
        handle_memory_request
    )

    MILLIE_AVAILABLE = True

except Exception as e:

    print("MILLIE IMPORT ERROR:", e)

    MILLIE_AVAILABLE = False

# =========================================================
# TANIA TASK AGENT
# =========================================================
try:

    from agents.tania.tania import (
        should_handle as tania_should_handle
    )

    from agents.tania.tania import (
        handle_task_request
    )

    TANIA_AVAILABLE = True

except Exception as e:

    print("TANIA IMPORT ERROR:", e)

    TANIA_AVAILABLE = False

# =========================================================
# CALLIE CALENDAR AGENT
# =========================================================
try:

    from agents.callie.callie import (
        should_handle as callie_should_handle
    )

    from agents.callie.callie import (
        handle_calendar_request
    )

    CALLIE_AVAILABLE = True

except Exception as e:

    print("CALLIE IMPORT ERROR:", e)

    CALLIE_AVAILABLE = False

# =========================================================
# EMILY EMAIL AGENT
# =========================================================
try:

    from agents.emily.emily import (
        should_handle as emily_should_handle
    )

    from agents.emily.emily import (
        handle_email_request
    )

    EMILY_AVAILABLE = True

except Exception as e:

    print("EMILY IMPORT ERROR:", e)

    EMILY_AVAILABLE = False

# =========================================================
# BRITTANY BROWSER AGENT
# =========================================================
try:
    from agents.brittany_browser.brittany import should_handle as brittany_should_handle
    from agents.brittany_browser.brittany import investigate as brittany_investigate
    BRITTANY_AVAILABLE = True
except Exception as e:
    print("BRITTANY IMPORT ERROR:", e)
    BRITTANY_AVAILABLE = False


app.add_middleware(
    CORSMiddleware,

    allow_origins=[

        "https://shine-l.netlify.app",

        "https://shine-l-production.up.railway.app"

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

    expose_headers=["*"]
)

UPLOAD_DIR = "uploads"
LIFE_STORY_FILE = "memory/life_story.json"
PROFILE_FILE = "memory/profile.json"
CONVERSATION_FILE = "memory/conversations.json"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("memory", exist_ok=True)


class ChatRequest(BaseModel):
    message: str


DRIFT_TRIGGERS = [
    "confused",
    "overwhelmed",
    "lost",
    "drifting",
    "too much",
    "slow down",
    "not making sense",
    "reset",
    "spiraling",
    "panic",
    "anxious",
]

GROUNDING_RESPONSE = """
Doug may be drifting or overwhelmed.

Slow down.
Reduce information density.
Use short sections.
Use calm pacing.
Use clear next steps.
Prioritize clarity, safety, orientation, and one next action.
"""

MEMORY_IMPORTANCE = {
    "kids": 10,
    "children": 10,
    "iyla": 10,
    "ashton": 10,
    "luella": 10,
    "mehlia": 10,
    "army": 9,
    "east timor": 10,
    "kapooka": 9,
    "deployment": 9,
    "recovery": 10,
    "na": 10,
    "aa": 10,
    "stepwork": 9,
    "shine": 10,
    "purpose": 9,
    "identity": 8,
    "trauma": 9,
    "family": 10,
    "clarity": 8,
}

SEMANTIC_LINKS = {
    "east timor": [
        "army",
        "kapooka",
        "transport",
        "military",
        "enlistment",
        "deployment",
        "reserve scheme",
        "timor",
    ],
    "army": [
        "kapooka",
        "east timor",
        "transport corps",
        "deployment",
        "reserve scheme",
        "military",
    ],
    "school": [
        "girls",
        "childhood",
        "grade",
        "growing up",
        "teenage",
        "adolescence",
    ],
    "recovery": [
        "na",
        "aa",
        "meetings",
        "addiction",
        "stepwork",
        "sobriety",
        "clean",
    ],
    "family": [
        "kids",
        "children",
        "mehlia",
        "luella",
        "iyla",
        "ashton",
    ],
}


def safe_load_json(path, fallback):
    try:
        if not os.path.exists(path):
            return fallback

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print("JSON LOAD ERROR:", path, e)
        return fallback


def safe_save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print("JSON SAVE ERROR:", path, e)


def load_profile():
    return safe_load_json(PROFILE_FILE, {})


def calculate_memory_score(text):
    score = 0
    text_lower = text.lower()

    for key, value in MEMORY_IMPORTANCE.items():
        if key in text_lower:
            score += value

    return score


def detect_drift(user_text):
    text = user_text.lower()
    return any(trigger in text for trigger in DRIFT_TRIGGERS)


def detect_intent(user_text):
    text = user_text.lower()

    if (
        "full file" in text
        or "full document" in text
        or "read full" in text
        or "show full" in text
        or "word for word" in text
        or "read the full" in text
        or "full story" in text
    ):
        return "full_recall"

    if (
        "remember" in text
        or "recall" in text
        or "what do you know" in text
        or "tell me about" in text
        or "what matters" in text
    ):
        return "memory_recall"

    return "normal"


def expand_search_terms(query):
    query_lower = query.lower()
    terms = [query_lower]

    words = query_lower.replace("?", "").replace(".", "").split()
    terms.extend(words)

    for key, linked_terms in SEMANTIC_LINKS.items():
        if key in query_lower:
            terms.extend(linked_terms)

    return list(set([t.strip() for t in terms if t.strip()]))


def search_life_story(query):
    stories = safe_load_json(LIFE_STORY_FILE, [])

    if not isinstance(stories, list):
        return []

    search_terms = expand_search_terms(query)
    matches = []

    for item in stories:
        title = str(item.get("title", ""))
        preview = str(item.get("preview", ""))
        full_content = str(
            item.get("full_content", item.get("content", ""))
        )

        text_blob = f"{title} {preview} {full_content}".lower()

        score = 0

        for term in search_terms:
            if term in text_blob:
                score += 1

        score += int(item.get("score", 0))

        if score > 0:
            copy_item = dict(item)
            copy_item["_score"] = score
            matches.append(copy_item)

    matches.sort(key=lambda x: x.get("_score", 0), reverse=True)

    return matches[:5]


def save_to_life_story(title, content_text):
    stories = safe_load_json(LIFE_STORY_FILE, [])

    if not isinstance(stories, list):
        stories = []

    preview_text = content_text[:3000]
    memory_score = calculate_memory_score(content_text)

    entry = {
        "title": title,
        "preview": preview_text,
        "full_content": content_text,
        "score": memory_score,
    }

    stories.append(entry)
    safe_save_json(LIFE_STORY_FILE, stories)



def save_conversation_turn(user_msg, assistant_reply):

    try:

        conversations = safe_load_json(
            CONVERSATION_FILE,
            []
        )

        entry = {

            "timestamp": str(datetime.now()),

            "user": user_msg,

            "assistant": assistant_reply

        }

        conversations.append(entry)

        safe_save_json(
            CONVERSATION_FILE,
            conversations
        )

    except Exception as e:

        print(
            "CONVERSATION SAVE ERROR:",
            e
        )


def build_profile_context():
    profile = load_profile()

    if not profile:
        return ""

    return "\n\nCANONICAL PROFILE MEMORY:\n" + json.dumps(
        profile,
        indent=2,
        ensure_ascii=False,
    )



def build_recent_conversation_context():

    try:

        conversations = safe_load_json(
            CONVERSATION_FILE,
            []
        )

        if not conversations:
            return ""

        recent = conversations[-10:]

        context = "\n\nRECENT CONVERSATIONS:\n"

        for convo in recent:

            context += (
                "\nUSER: "
                + convo.get("user","")
            )

            context += (
                "\nL: "
                + convo.get("assistant","")
            )

            context += "\n"

        return context

    except Exception as e:

        print(
            "CONVO CONTEXT ERROR:",
            e
        )

        return ""


def build_story_context(user_msg):
    matches = search_life_story(user_msg)

    if not matches:
        return ""

    story_context = "\n\nRELEVANT STORY MEMORY:\n"

    for item in matches:
        story_context += "\n--- STORY MEMORY ---\n"
        story_context += item.get("preview", "")

    return story_context


@app.get("/")
def root():
    return {
        "status": "L SERVER RUNNING",
        "version": "clean-server-v2",
        "memory": "connected",
        "cors": "enabled",
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    user_msg = req.message

    # ==========================================
    # LIVE BRISBANE TIME
    # ==========================================

    current_time = datetime.now(
        ZoneInfo("Australia/Brisbane")
    )

    time_context = f"""

CURRENT DATE/TIME:
{current_time.strftime("%A %d %B %Y")}
{current_time.strftime("%I:%M %p")}

Timezone:
Australia/Brisbane

"""
    print("\nUSER MESSAGE:", user_msg)

    intent = detect_intent(user_msg)

    



    





    # =====================================================
    # ADDIE TASK ROUTING
    # =====================================================

    if (
        ADDIE_AVAILABLE
        and addie_should_handle(user_msg)
    ):

        print("\n✅ ROUTING TO ADDIE TASK EXECUTION")

        addie_reply = addie_handle_task_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "✅ Addie Task Execution:\n\n"
            + addie_reply
        )

        return {
            "reply":
                "✅ Addie Task Execution:\n\n"
                + addie_reply
        }

    # =====================================================
    # EMME EMOTIONAL ROUTING
    # =====================================================

    if (
        EMME_AVAILABLE
        and emme_should_handle(user_msg)
    ):

        print("\n❤️ ROUTING TO EMME EMOTIONAL SUPPORT")

        emme_reply = handle_emotional_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "❤️ Emme Emotional Support:\n\n"
            + emme_reply
        )

        return {
            "reply":
                "❤️ Emme Emotional Support:\n\n"
                + emme_reply
        }

    # =====================================================
    # MILLIE MEMORY ROUTING
    # =====================================================

    if (
        MILLIE_AVAILABLE
        and millie_should_handle(user_msg)
    ):

        print("\n🧠 ROUTING TO MILLIE MEMORY KEEPER")

        millie_reply = handle_memory_request(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🧠 Millie Memory Keeper:\n\n"
            + millie_reply
        )

        return {
            "reply":
                "🧠 Millie Memory Keeper:\n\n"
                + millie_reply
        }

    # =====================================================
    # PIXIE IMAGE ROUTING
    # =====================================================

    if (
        PIXIE_AVAILABLE
        and pixie_should_handle(user_msg)
    ):

        print("\n🎨 ROUTING TO PIXIE")

        try:

            result = pixie_create_image(
                user_msg
            )

            if not result:

                return {
                    "reply":
                        "❌ Pixie returned no image result."
                }

            return {
                "reply":
                    result.get(
                        "reply",
                        "Pixie created an image."
                    ),

                "image_url":
                    result.get(
                        "image_url",
                        ""
                    )
            }

        except Exception as e:

            print(
                "PIXIE GENERATION ERROR:",
                e
            )

            return {
                "reply":
                    "❌ Pixie generation failed:\n\n"
                    + str(e)
            }

    # =====================================================
    # TANIA TASK ROUTING
    # =====================================================

    if (
        TANIA_AVAILABLE
        and tania_should_handle(user_msg)
    ):

        print("\n✅ ROUTING TO TANIA")

        tania_reply = (
            handle_task_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "✅ Tania Tasks:\n\n"
            + tania_reply
        )

        return {
            "reply":
                "✅ Tania Tasks:\n\n"
                + tania_reply
        }

    # =====================================================
    # CALLIE CALENDAR ROUTING
    # =====================================================

    if (
        CALLIE_AVAILABLE
        and callie_should_handle(user_msg)
    ):

        print("\n📅 ROUTING TO CALLIE")

        callie_reply = (
            handle_calendar_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "📅 Callie Calendar:\n\n"
            + callie_reply
        )

        return {
            "reply":
                "📅 Callie Calendar:\n\n"
                + callie_reply
        }

    # =====================================================
    # EMILY EMAIL ROUTING
    # =====================================================

    if (
        EMILY_AVAILABLE
        and emily_should_handle(user_msg)
    ):

        print("\n📧 ROUTING TO EMILY EMAIL")

        emily_reply = (
            handle_email_request(user_msg)
        )

        save_conversation_turn(
            user_msg,
            "📧 Emily Email:\n\n"
            + emily_reply
        )

        return {
            "reply":
                "📧 Emily Email:\n\n"
                + emily_reply
        }

    # =====================================================
    # BRITTANY ROUTING V1
    # =====================================================

    if (
        BRITTANY_AVAILABLE
        and brittany_should_handle(user_msg)
    ):

        print("\n🌐 ROUTING TO BRITTANY BROWSER")

        brittany_reply = brittany_investigate(
            user_msg
        )

        save_conversation_turn(
            user_msg,
            "🌐 Brittany Browser:\n\n"
            + brittany_reply
        )

        return {
            "reply":
                "🌐 Brittany Browser:\n\n"
                + brittany_reply
        }


    if intent == "full_recall":
        matches = search_life_story(user_msg)

        if not matches:
            return {
                "reply": "I could not find a matching full story file in memory."
            }

        response_text = ""

        for item in matches:
            response_text += (
                "\n\n====================\n"
                + item.get("title", "Untitled")
                + "\n====================\n\n"
                + item.get("full_content", item.get("preview", ""))
            )

        return {"reply": response_text}

    process(user_msg)

    memory_context = build_context()
    state = detect_emotional_state(user_msg)
    tone = generate_emotional_tone(state)

    system_prompt = f"""
You are L, Doug's personal AI companion.

{time_context}

You have persistent memory.

Here is the current memory context:

{memory_context}

Tone instruction:
{tone}

Instructions:
- Use memory when answering.
- Use canonical profile facts as the highest authority.
- If the user asks about their children, answer from canonical profile first.
- If story memory is provided, use it.
- Do not claim you cannot access memory if memory context is provided.
- Be calm, clear, warm, and direct.
"""

    system_prompt += build_profile_context()

    system_prompt += (
        build_recent_conversation_context()
    )

    if intent == "memory_recall":
        system_prompt += build_story_context(user_msg)

    if detect_drift(user_msg):
        system_prompt += GROUNDING_RESPONSE

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
    )

    reply = response.choices[0].message.content

    print("\nL RESPONSE:", reply)

    save_conversation_turn(
        user_msg,
        reply
    )

    return {"reply": reply}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_text = ""

    if file.filename.lower().endswith(".pdf"):
        try:
            doc = fitz.open(file_path)

            for page in doc:
                file_text += page.get_text()

            doc.close()

            process(f"User uploaded PDF: {file.filename}")
            save_to_life_story(file.filename, file_text)

            return {
                "status": "success",
                "filename": file.filename,
                "preview": file_text[:3000],
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"PDF read failed: {str(e)}",
            }

    if file.filename.lower().endswith(".txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_text = f.read()

            process(f"User uploaded TXT: {file.filename}")
            save_to_life_story(file.filename, file_text)

            return {
                "status": "success",
                "filename": file.filename,
                "preview": file_text[:3000],
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"TXT read failed: {str(e)}",
            }

    if (
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
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Read and analyze this image. "
                                    "If it contains handwriting or document text, "
                                    "extract as much text as possible and then summarize it clearly."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
            )

            vision_text = vision_response.choices[0].message.content

            process(f"User uploaded image: {file.filename}")
            save_to_life_story(file.filename, vision_text)

            return {
                "status": "success",
                "filename": file.filename,
                "preview": vision_text,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Image analysis failed: {str(e)}",
            }

    return {
        "status": "uploaded",
        "filename": file.filename,
        "message": "File uploaded successfully.",
    }


@app.post("/recall")
async def recall_story(req: ChatRequest):
    matches = search_life_story(req.message)

    if not matches:
        return {
            "reply": "I could not find anything in your story memory about that yet."
        }

    reply = ""

    for i, item in enumerate(matches):
        reply += f"\n\n--- MEMORY {i + 1} ---\n"
        reply += item.get("full_content", item.get("preview", ""))

    return {"reply": reply}


@app.get("/stories")
async def get_stories():
    stories = safe_load_json(LIFE_STORY_FILE, [])

    if not isinstance(stories, list):
        stories = []

    clean_stories = []

    for item in stories:
        clean_stories.append(
            {
                "title": item.get("title", "Untitled"),
                "preview": item.get("preview", ""),
                "full_content": item.get(
                    "full_content",
                    item.get("content", ""),
                ),
                "score": item.get("score", 0),
            }
        )

    return {"stories": clean_stories[::-1]}



# =========================================================
# BRITTANY DIRECT TEST ENDPOINT
# =========================================================
@app.post("/brittany")
async def brittany_direct(req: ChatRequest):

    if not BRITTANY_AVAILABLE:

        return {
            "reply": "Brittany Browser is not available yet."
        }

    result = brittany_investigate(req.message)

    return {
        "reply": result
    }




# =========================================================
# EMILY DIRECT TEST ENDPOINT
# =========================================================
@app.post("/emily")
async def emily_direct(req: ChatRequest):

    if not EMILY_AVAILABLE:

        return {
            "reply":
                "Emily Email is not available."
        }

    result = handle_email_request(
        req.message
    )

    return {
        "reply": result
    }





# =========================================================
# GOOGLE AUTH ROUTES
# =========================================================

@app.get("/google/status")
async def google_connection_status():

    if not GOOGLE_AUTH_AVAILABLE:

        return {
            "connected": False,
            "error": "Google auth module is not available."
        }

    return google_status()


@app.get("/google/auth/start")
async def google_auth_start():

    if not GOOGLE_AUTH_AVAILABLE:

        return {
            "error": "Google auth module is not available."
        }

    auth_url = build_auth_url()

    return RedirectResponse(auth_url)


@app.get("/google/auth/callback")
async def google_auth_callback(request: Request):

    if not GOOGLE_AUTH_AVAILABLE:

        return HTMLResponse(
            "<h2>Google auth module is not available.</h2>"
        )

    full_url = str(request.url)

    try:

        result = handle_callback(full_url)

        return HTMLResponse(
            """
            <html>
                <body style="font-family:Arial;padding:40px;">
                    <h1>✅ Google Connected</h1>
                    <p>Emily, Callie, and Tania can now use the shared Google auth layer.</p>
                    <p>You can close this tab and return to Shine L.</p>
                </body>
            </html>
            """
        )

    except Exception as e:

        return HTMLResponse(
            f"""
            <html>
                <body style="font-family:Arial;padding:40px;">
                    <h1>❌ Google Connection Failed</h1>
                    <pre>{str(e)}</pre>
                </body>
            </html>
            """
        )


@app.get("/google/auth/reset")
async def google_auth_reset():

    if not GOOGLE_AUTH_AVAILABLE:

        return {
            "error": "Google auth module is not available."
        }

    clear_credentials()

    return {
        "status": "reset",
        "message": "Google token cleared. Reconnect via /google/auth/start"
    }


# =====================================================
# APPROVAL → EXECUTION LAYER
# =====================================================

LAST_HANDOFFS = {
    "calendar": [],
    "tasks": []
}

# =====================================================
# STORE HANDOFFS
# =====================================================

def store_handoffs(calendar_items, task_items):

    global LAST_HANDOFFS

    LAST_HANDOFFS["calendar"] = calendar_items
    LAST_HANDOFFS["tasks"] = task_items

# =====================================================
# EXECUTE TASKS
# =====================================================

def execute_task_handoffs():

    from agents.tania import (
        create_task_from_handoff
    )

    created = []

    for task in LAST_HANDOFFS["tasks"]:

        result = create_task_from_handoff(task)

        created.append(result)

    return created

# =====================================================
# EXECUTE CALENDAR
# =====================================================

def execute_calendar_handoffs():

    from agents.callie import (
        create_event_from_handoff
    )

    created = []

    for item in LAST_HANDOFFS["calendar"]:

        result = create_event_from_handoff(item)

        created.append(result)

    return created


# =====================================================
# SMART AGENT INTENT ROUTER
# =====================================================

def handle_agent_name_only(message: str):

    text = message.lower().strip()

    # =================================================
    # TANIA
    # =================================================

    if text == "tania":

        return """

# ✅ Tania

Would you like me to:

1. Check your tasks
2. Create a new task
3. Review priorities
4. Something else

"""

    # =================================================
    # CALLIE
    # =================================================

    if text == "callie":

        return """

# 📅 Callie

Would you like me to:

1. Check your calendar
2. Create an event
3. Review schedule
4. Something else

"""

    # =================================================
    # EMILY
    # =================================================

    if text == "emily":

        return """

# 📧 Emily

Would you like me to:

1. Check your emails
2. Summarize inbox
3. Review priorities
4. Something else

"""

    return None
















