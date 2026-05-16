import json
import os


def safe_load_json(path, fallback):

    try:

        if not os.path.exists(path):
            return fallback

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:

        print("JSON LOAD ERROR:", path, e)

        return fallback


def safe_save_json(path, data):

    try:

        with open(path, "w", encoding="utf-8") as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("JSON SAVE ERROR:", path, e)
