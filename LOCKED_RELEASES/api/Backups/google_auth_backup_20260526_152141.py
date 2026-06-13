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
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify"
]

# =====================================================
# TOKEN PATH
# =====================================================

TOKEN_PATH = ROOT / "configs" / "token.json"

# =====================================================
# TEMP CREDS PATH
# =====================================================

TEMP_CREDS_PATH = "/tmp/google_credentials.json"

# =====================================================
# BUILD CREDS FILE FROM ENV
# =====================================================

google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

if not google_creds_json:

    raise Exception(
        "GOOGLE_CREDENTIALS_JSON missing from Railway variables"
    )

creds_data = json.loads(google_creds_json)

with open(TEMP_CREDS_PATH, "w") as f:

    json.dump(creds_data, f)

# =====================================================
# AUTH FUNCTION
# =====================================================

def get_google_creds():

    creds = None

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
                TEMP_CREDS_PATH,
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
