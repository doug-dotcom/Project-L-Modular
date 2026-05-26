import csv
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "uploads"

def find_latest_csv():
    if not UPLOADS.exists():
        return None

    files = list(UPLOADS.glob("*.csv"))

    if not files:
        return None

    return max(files, key=lambda p: p.stat().st_mtime)

def parse_amount(value):
    try:
        clean = str(value).replace("$", "").replace(",", "").strip()
        return float(clean)
    except Exception:
        return 0.0

def analyse_latest_csv():
    latest = find_latest_csv()

    if not latest:
        return "# 💰 Fiona Finance\n\nI could not find an uploaded CSV file yet."

    rows = []

    with open(latest, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(row)

    if not rows:
        return f"# 💰 Fiona Finance\n\nI found `{latest.name}`, but it appears empty."

    headers = list(rows[0].keys())

    amount_col = None
    desc_col = None
    date_col = None

    for h in headers:
        low = h.lower()

        if amount_col is None and any(x in low for x in ["amount", "value", "debit", "credit"]):
            amount_col = h

        if desc_col is None and any(x in low for x in ["description", "merchant", "name", "narrative"]):
            desc_col = h

        if date_col is None and "date" in low:
            date_col = h

    if amount_col is None:
        for h in headers:
            for row in rows[:20]:
                try:
                    float(str(row.get(h, "")).replace(",", ""))
                    amount_col = h
                    break
                except Exception:
                    pass
            if amount_col:
                break

    total_in = 0.0
    total_out = 0.0
    merchants = defaultdict(float)
    examples = []

    for row in rows:
        amount = parse_amount(row.get(amount_col, 0)) if amount_col else 0.0
        desc = str(row.get(desc_col, "Unknown")).strip() if desc_col else "Unknown"

        if amount >= 0:
            total_in += amount
        else:
            total_out += abs(amount)
            merchants[desc] += abs(amount)

        if len(examples) < 8:
            examples.append((row.get(date_col, ""), desc, amount))

    top_merchants = sorted(
        merchants.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    reply = f"""
# 💰 Fiona Finance — CSV Review

I found and reviewed:

`{latest.name}`

## File Summary

- Rows reviewed: {len(rows)}
- Amount column detected: `{amount_col}`
- Description column detected: `{desc_col}`
- Date column detected: `{date_col}`

## Money Movement

- Total incoming: ${total_in:,.2f}
- Total outgoing: ${total_out:,.2f}
- Net movement: ${(total_in - total_out):,.2f}

## Largest Spending / Merchant Patterns
"""

    for name, amount in top_merchants:
        reply += f"\n- {name}: ${amount:,.2f}"

    reply += """

## Sample Transactions
"""

    for date, desc, amount in examples:
        reply += f"\n- {date} | {desc} | ${amount:,.2f}"

    reply += """

## Fiona Note

This is an early calm finance review. I can now see the uploaded CSV and summarise spending patterns. Next upgrade should add categories, recurring bill detection, and monthly cashflow grouping.
"""

    return reply
