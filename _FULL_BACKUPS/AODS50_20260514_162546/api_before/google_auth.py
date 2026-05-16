import os
import json
from typing import Optional

from supabase import create_client

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# =====================================================
# CONFIG
# =====================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

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

TOKEN_KEY = "google_shared_token"

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
# TOKEN STORAGE — SUPABASE
# =====================================================

def save_credentials(creds: Credentials):

    token_json = creds.to_json()

    existing = (
        supabase.table("system_memory")
        .select("*")
        .eq("key", TOKEN_KEY)
        .execute()
    )

    payload = {
        "key": TOKEN_KEY,
        "value": token_json
    }

    if existing.data:

        (
            supabase.table("system_memory")
            .update(payload)
            .eq("key", TOKEN_KEY)
            .execute()
        )

    else:

        (
            supabase.table("system_memory")
            .insert(payload)
            .execute()
        )

def load_credentials() -> Optional[Credentials]:

    try:

        result = (
            supabase.table("system_memory")
            .select("*")
            .eq("key", TOKEN_KEY)
            .execute()
        )

        if not result.data:
            return None

        token_json = result.data[0]["value"]

        token_data = json.loads(token_json)

        return Credentials.from_authorized_user_info(
            token_data,
            SCOPES
        )

    except Exception as e:

        print("GOOGLE TOKEN LOAD ERROR:", e)

        return None

def clear_credentials():

    (
        supabase.table("system_memory")
        .delete()
        .eq("key", TOKEN_KEY)
        .execute()
    )

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
