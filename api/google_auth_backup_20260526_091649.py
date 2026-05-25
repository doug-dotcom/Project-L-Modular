import os
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

TOKEN_DIR = os.path.join(
    ROOT,
    "tokens"
)

os.makedirs(
    TOKEN_DIR,
    exist_ok=True
)

SCOPES = {

    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly"
    ],

    "calendar": [
        "https://www.googleapis.com/auth/calendar.readonly"
    ]

}

def get_google_service(service_name, version):

    creds = None

    token_file = os.path.join(
        TOKEN_DIR,
        f"{service_name}_token.pickle"
    )

    credentials_file = os.path.join(
        ROOT,
        "credentials.json"
    )

    scopes = SCOPES.get(service_name, [])

    if os.path.exists(token_file):

        with open(token_file, "rb") as token:

            creds = pickle.load(token)

    if creds and creds.expired and creds.refresh_token:

        creds.refresh(Request())

    elif not creds:

        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file,
            scopes
        )

        creds = flow.run_local_server(port=0)

        with open(token_file, "wb") as token:

            pickle.dump(creds, token)

    service = build(
        service_name,
        version,
        credentials=creds
    )

    return service
