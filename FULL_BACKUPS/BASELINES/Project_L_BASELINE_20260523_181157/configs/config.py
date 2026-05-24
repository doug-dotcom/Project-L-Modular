import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

L_PORT = int(
    os.getenv("L_PORT", 8000)
)

L_HOST = os.getenv(
    "L_HOST",
    "0.0.0.0"
)

DEBUG = (
    os.getenv("DEBUG", "false").lower()
    == "true"
)

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "unsafe-dev-secret"
)

MEMORY_LIMIT = int(
    os.getenv("MEMORY_LIMIT", 5000)
)
