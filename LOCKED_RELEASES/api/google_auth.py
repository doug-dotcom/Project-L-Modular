import os
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

# =====================================================
# SCOPES
# =====================================================

SCOPES = [

    # =========================
    # CALENDAR
    # =========================

    "https://www.googleapis.com/auth/calendar",

    # =========================
    # GMAIL
    # =========================

    "https://www.googleapis.com/auth/gmail.modify",

    # =========================
    # TASKS
    # =========================

    "https://www.googleapis.com/auth/tasks",

    # =========================
    # DRIVE
    # =========================

    "https://www.googleapis.com/auth/drive.file",

    # =========================
    # USER PROFILE
    # =========================

    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

# =====================================================
# TOKEN PATH
# =====================================================

TOKEN_PATH = ROOT / "configs" / "token.json"

# =====================================================
# TEMP CREDS PATH
# =====================================================

TEMP_CREDS_PATH = ROOT / "configs" / "temp_google_credentials.json"

# =====================================================
# LOAD CREDS
# =====================================================

google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

# =====================================================
# LOCAL FALLBACK
# =====================================================

if not google_creds_json:

    local_creds = ROOT / "configs" / "credentials.json"

    if local_creds.exists():

        with open(local_creds, "r") as f:

            creds_data = json.load(f)

        print("[LOCAL] Using local credentials.json")

    else:

        raise Exception(
            "No Google credentials found"
        )

else:

    creds_data = json.loads(google_creds_json)

    print("[RAILWAY] Using GOOGLE_CREDENTIALS_JSON")

# =====================================================
# ALWAYS CREATE TEMP FILE
# =====================================================

with open(TEMP_CREDS_PATH, "w") as f:

    json.dump(creds_data, f)

# =====================================================
# AUTH FUNCTION
# =====================================================

def get_google_creds():

    creds = None

    # =================================================
    # GOOGLE TOKEN ENV
    # =================================================

    google_token_json = os.getenv(
        "GOOGLE_TOKEN_JSON"
    )

    if google_token_json:

        token_data = json.loads(
            google_token_json
        )

        TOKEN_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(TOKEN_PATH, "w") as f:

            json.dump(token_data, f)

        print(
            "[RAILWAY] Using GOOGLE_TOKEN_JSON"
        )

    # =================================================
    # LOAD TOKEN
    # =================================================

    if TOKEN_PATH.exists():

        creds = Credentials.from_authorized_user_file(
            str(TOKEN_PATH),
            SCOPES
        )

    # =================================================
    # REFRESH / LOGIN
    # =================================================

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:

            creds.refresh(Request())

        else:

            flow = InstalledAppFlow.from_client_secrets_file(
                str(TEMP_CREDS_PATH),
                SCOPES
            )

            creds = flow.run_local_server(port=0)

        # =============================================
        # SAVE TOKEN
        # =============================================

        TOKEN_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(TOKEN_PATH, "w") as token:

            token.write(creds.to_json())

    return creds

# =====================================================
# GOOGLE SERVICE BUILDER
# =====================================================

from googleapiclient.discovery import build

def get_google_service(
    service_name="calendar",
    version="v3"
):

    creds = get_google_creds()

    return build(
        service_name,
        version,
        credentials=creds
    )



