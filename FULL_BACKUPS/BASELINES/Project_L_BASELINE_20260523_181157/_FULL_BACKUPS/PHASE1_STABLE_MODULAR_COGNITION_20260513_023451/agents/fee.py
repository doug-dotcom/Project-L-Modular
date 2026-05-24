import csv
import os
import json
from collections import defaultdict

FROLLO_DIR = "C:/Shine_L/memory/frollo"
OUTPUT_PATH = "C:/Shine_L/memory/finance.json"

def load_data():
    try:
        with open(OUTPUT_PATH, "r") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

def import_frollo():
    data = []

    files = os.listdir(FROLLO_DIR)
    if not files:
        return "No CSV files found in frollo folder."

    for file in files:
        if file.endswith(".csv"):
            path = os.path.join(FROLLO_DIR, file)

            with open(path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    try:
                        amount = float(row.get("Amount", 0))
                    except:
                        continue

                    entry = {
                        "date": row.get("Date"),
                        "merchant": row.get("Description") or row.get("Merchant"),
                        "amount": amount
                    }

                    data.append(entry)

    save_data(data)
    return f"Imported {len(data)} transactions."

def analyse_spending():
    data = load_data()

    if not data:
        return "No financial data available."

    total_spent = sum(abs(d["amount"]) for d in data if d["amount"] < 0)

    merchants = defaultdict(float)
    for d in data:
        if d["amount"] < 0:
            merchants[d["merchant"]] += abs(d["amount"])

    top = sorted(merchants.items(), key=lambda x: x[1], reverse=True)[:5]

    response = f"You’ve spent about  recently.\n\nTop spending:\n"

    for m, amt in top:
        response += f"- {m}: \n"

    return response

def detect_bills():
    data = load_data()

    merchants = defaultdict(list)

    for d in data:
        if d["amount"] < 0:
            merchants[d["merchant"]].append(d["amount"])

    recurring = []
    for m, txns in merchants.items():
        if len(txns) >= 3:
            avg = sum(abs(x) for x in txns) / len(txns)
            recurring.append((m, round(avg, 2)))

    if not recurring:
        return "No recurring bills detected yet."

    response = "These look like recurring bills:\n\n"
    total = 0

    for m, amt in recurring:
        total += amt
        response += f"- {m}: ~/month\n"

    response += f"\nEstimated monthly bills: "
    response += f"\nSuggested weekly top-up: "

    return response
