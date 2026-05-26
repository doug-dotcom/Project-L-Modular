from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

UPLOAD_ROOT = ROOT / "uploads"

def get_upload_inventory():

    inventory = {}

    folders = [

        "csv",
        "pdf",
        "images",
        "docs",
        "finance",
        "medical",
        "legal",
        "memory",
        "archive"

    ]

    for folder in folders:

        path = UPLOAD_ROOT / folder

        if not path.exists():

            inventory[folder] = []

            continue

        files = [

            f.name

            for f in path.iterdir()

            if f.is_file()

        ]

        inventory[folder] = files

    return inventory

def latest_file(folder):

    path = UPLOAD_ROOT / folder

    if not path.exists():

        return None

    files = [

        f for f in path.iterdir()

        if f.is_file()
    ]

    if not files:

        return None

    return max(
        files,
        key=lambda p: p.stat().st_mtime
    )
