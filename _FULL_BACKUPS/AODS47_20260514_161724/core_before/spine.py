import json

PROFILE_PATH = "C:/Shine_L/memory/doug_profile.json"

def load_profile():
    try:
        with open(PROFILE_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

profile = load_profile()
import os
from openai import OpenAI

client = OpenAI(api_key=open("C:/Shine_L/configs/openai_key.txt").read().strip())

def handle_request(user_msg: str):

    msg = (user_msg or "").lower().strip()

    # --- SYSTEM FIRST (AODS style) ---
    if not msg:
        return "Say something 👊"

    if "hello" in msg or "awake" in msg:
        return "I’m here 👊 — system online and stable."

    if "plan" in msg:
        return "Let’s keep it simple 👊 — what’s the one thing that matters?"

    # --- AI FALLBACK ---
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are L. You are supporting Doug. Keep responses simple, grounded, and aligned with his system. Calm, clear, supportive. Keep answers simple and grounded."},
                {"role": "user", "content": user_msg}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"AI not responding 👊 — {str(e)}"

