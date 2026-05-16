import os
import json
from collections import defaultdict
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

FINANCE_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "fiona_finance.json"
)

os.makedirs(
    os.path.dirname(FINANCE_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(FINANCE_FILE):

            return []

        with open(
            FINANCE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("FIONA LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            FINANCE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("FIONA SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "fiona",
        "finance",
        "spending",
        "budget",
        "money",
        "expenses",
        "financial",
        "analyze spending",
        "track spending",
        "banking",
        "cashflow"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# DETECT CATEGORY
# =====================================================

def detect_category(text):

    lower = text.lower()

    categories = {

        "food": [
            "food",
            "coffee",
            "restaurant",
            "cafe",
            "ubereats"
        ],

        "transport": [
            "fuel",
            "uber",
            "taxi",
            "transport"
        ],

        "subscriptions": [
            "subscription",
            "netflix",
            "spotify",
            "apple"
        ],

        "shopping": [
            "shopping",
            "amazon",
            "store",
            "purchase"
        ]
    }

    for category, words in categories.items():

        if any(word in lower for word in words):

            return category

    return "general"

# =====================================================
# EXTRACT AMOUNT
# =====================================================

def extract_amount(text):

    import re

    match = re.search(
        r"\$?(\d+(\.\d+)?)",
        text
    )

    if match:

        try:

            return float(match.group(1))

        except:
            return 0

    return 0

# =====================================================
# SAVE TRANSACTION
# =====================================================

def save_transaction(message):

    data = _load()

    amount = extract_amount(message)

    category = detect_category(message)

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "message":
            message,

        "amount":
            amount,

        "category":
            category

    }

    data.append(entry)

    _save(data)

    return entry

# =====================================================
# BUILD FINANCE SUMMARY
# =====================================================

def build_summary():

    data = _load()

    if not data:

        return (
            "# 💰 Fiona Finance Cognition\n\n"
            "No financial records stored yet."
        )

    total = sum(
        d.get("amount",0)
        for d in data
    )

    categories = defaultdict(float)

    for d in data:

        categories[
            d.get("category","general")
        ] += d.get("amount",0)

    reply = "# 💰 Fiona Finance Cognition\n\n"

    reply += (
        f"Tracked Total: ${round(total,2)}\n\n"
    )

    reply += "## Spending Categories\n\n"

    for category, amount in categories.items():

        reply += (
            f"- {category}: "
            f"${round(amount,2)}\n"
        )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_finance_request(message: str):

    text = message.lower()

    if (
        "summary" in text
        or "analyze" in text
        or "show spending" in text
    ):

        return build_summary()

    entry = save_transaction(message)

    return (
        "# 💰 Fiona Finance Cognition\n\n"
        "Financial item recorded successfully.\n\n"
        "Amount: $"
        + str(entry.get("amount",0))
        + "\n\nCategory: "
        + entry.get("category","general")
    )
