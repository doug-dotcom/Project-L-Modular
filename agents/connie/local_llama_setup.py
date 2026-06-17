# =====================================================
# LOCAL LLAMA SETUP
# TIER 5 - AODS 1
# =====================================================

from pathlib import Path
from typing import Dict


def check_local_llama_setup(
    model_path: str = "models"
) -> Dict:

    path = Path(
        model_path
    )

    exists = path.exists()

    model_files = []

    if exists:

        model_files = [

            str(file.name)

            for file in path.glob("*")

            if file.is_file()

        ]

    return {

        "agent":
            "Local Llama Setup",

        "model_path":
            str(path),

        "model_path_exists":
            exists,

        "model_file_count":
            len(model_files),

        "model_files":
            model_files,

        "ready":
            exists and len(model_files) > 0

    }


if __name__ == "__main__":

    test_path = "models"

    Path(test_path).mkdir(
        parents=True,
        exist_ok=True
    )

    result = check_local_llama_setup(
        test_path
    )

    print(result)

    assert result["model_path_exists"] is True

    assert "ready" in result

