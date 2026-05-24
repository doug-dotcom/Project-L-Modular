import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    ROOT
    / "memory"
    / "pending"
    / "pending_memory_queue.json"
)

# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    try:

        if not QUEUE_FILE.exists():
            return []

        return json.loads(

            QUEUE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return []

# ============================================================
# SAVE QUEUE
# ============================================================

def save_queue(queue):

    QUEUE_FILE.write_text(

        json.dumps(
            queue,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    text = str(text).strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text

# ============================================================
# COMPRESS MEMORY
# ============================================================

def compress_memory(content, domain):

    text = clean_text(content)

    lower = text.lower()

    # ========================================================
    # FAMILY COMPRESSION
    # ========================================================

    if domain == "family":

        replacements = [

            ("my daughter", "Doug's daughter"),
            ("my son", "Doug's son"),
            ("my kids", "Doug's children"),
            ("my family", "Doug's family")
        ]

        for old, new in replacements:

            lower = lower.replace(old, new)

        text = lower.capitalize()

    # ========================================================
    # IDENTITY COMPRESSION
    # ========================================================

    elif domain == "identity":

        if lower.startswith("i am"):
            text = (
                "Doug identifies as "
                + text[5:]
            )

        elif lower.startswith("my name is"):
            text = (
                "Doug's name is "
                + text[11:]
            )

    # ========================================================
    # HEALTH COMPRESSION
    # ========================================================

    elif domain == "health":

        if "adhd" in lower:
            text = (
                "Doug has ADHD-related context."
            )

    # ========================================================
    # PROJECT L COMPRESSION
    # ========================================================

    elif domain == "project_l":

        if "project l" in lower:
            text = (
                "Doug is actively building Project L."
            )

    return clean_text(text)

# ============================================================
# RUN COMPRESSION
# ============================================================

def compress_pending_memories():

    queue = load_queue()

    compressed = 0

    for item in queue:

        if item.get("status") != "classified":
            continue

        original = item.get(
            "content",
            ""
        )

        domain = item.get(
            "proposed_domain",
            "general"
        )

        compressed_text = compress_memory(
            original,
            domain
        )

        item["compressed_content"] = compressed_text

        item["compressed_at"] = str(
            datetime.now()
        )

        item["status"] = "compressed"

        compressed += 1

    save_queue(queue)

    return {

        "status": "ok",

        "compressed": compressed,

        "queue_size": len(queue)
    }

# ============================================================
# STATUS
# ============================================================

def compression_status():

    queue = load_queue()

    compressed = 0

    for item in queue:

        if item.get("status") == "compressed":
            compressed += 1

    return {

        "status": "online",

        "compressed": compressed,

        "queue_size": len(queue),

        "operation": "AODS-107"
    }
