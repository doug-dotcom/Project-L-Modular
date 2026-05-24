import os
import json
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# =====================================================
# CONFIG
# =====================================================

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
CONFIG_DIR = os.path.join(ROOT_DIR, "configs")

os.makedirs(CONFIG_DIR, exist_ok=True)

TOKEN_PATH = os.path.join(CONFIG_DIR, "google_token.json")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://shine-l-production.up.railway.app"
).rstrip("/")

REDIRECT_URI = f"{PUBLIC_BASE_URL}/google/auth/callback"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks"
]

# =====================================================
# CLIENT CONFIG
# =====================================================

def get_client_config():

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:

        raise Exception(
            "Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variables."
        )

    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                REDIRECT_URI
            ]
        }
    }

# =====================================================
# TOKEN STORAGE
# =====================================================

def save_credentials(creds: Credentials):

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

def load_credentials() -> Optional[Credentials]:

    if not os.path.exists(TOKEN_PATH):
        return None

    try:

        return Credentials.from_authorized_user_file(
            TOKEN_PATH,
            SCOPES
        )

    except Exception as e:

        print("GOOGLE TOKEN LOAD ERROR:", e)

        return None

def clear_credentials():

    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)

# =====================================================
# AUTH URL
# =====================================================

def build_auth_url():

    flow = Flow.from_client_config(
        get_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=False
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    return auth_url

# =====================================================
# CALLBACK HANDLER
# =====================================================

def handle_callback(full_callback_url: str):

    flow = Flow.from_client_config(
        get_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=False
    )

    flow.fetch_token(
        authorization_response=full_callback_url
    )

    creds = flow.credentials

    save_credentials(creds)

    return {
        "status": "connected",
        "scopes": SCOPES,
        "redirect_uri": REDIRECT_URI
    }

# =====================================================
# STATUS
# =====================================================

def google_status():

    creds = load_credentials()

    if not creds:

        return {
            "connected": False,
            "message": "Google is not connected.",
            "redirect_uri": REDIRECT_URI
        }

    if creds.expired and creds.refresh_token:

        try:

            creds.refresh(Request())

            save_credentials(creds)

        except Exception as e:

            return {
                "connected": False,
                "message": "Google token refresh failed.",
                "error": str(e),
                "redirect_uri": REDIRECT_URI
            }

    return {
        "connected": bool(creds and creds.valid),
        "expired": creds.expired,
        "has_refresh_token": bool(creds.refresh_token),
        "redirect_uri": REDIRECT_URI
    }

# =====================================================
# SHARED GOOGLE SERVICE
# =====================================================

def get_google_service(service_name: str, version: str):

    creds = load_credentials()

    if not creds:

        raise Exception(
            "Google is not connected. Visit /google/auth/start first."
        )

    if creds.expired and creds.refresh_token:

        creds.refresh(Request())

        save_credentials(creds)

    if not creds.valid:

        raise Exception(
            "Google credentials are invalid. Reconnect Google."
        )

    return build(
        service_name,
        version,
        credentials=creds
    )