from openai import OpenAI

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from orchestration.runtime_bootstrap import (
    build_runtime_stack,
    build_runtime_status
)

from services.runtime_endpoints import router as runtime_router

from utils.logger import (
    log_info,
    log_error,
    log_exception
)

# Runtime API


try:
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "user",
                "content": message
            }
        ]
    )

    reply = response.choices[0].message.content

except Exception as e:

    print(f"OPENAI ERROR: {e}")

    reply = "AI Error: Connection error."

