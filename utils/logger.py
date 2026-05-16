import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOG_DIR = ROOT / "logs"

LOG_DIR.mkdir(exist_ok=True)

RUNTIME_LOG = LOG_DIR / "runtime.log"
ERROR_LOG   = LOG_DIR / "errors.log"

# =====================================================
# MAIN LOGGER
# =====================================================

logger = logging.getLogger("project_l")

logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

# =====================================================
# RUNTIME HANDLER
# =====================================================

runtime_handler = logging.FileHandler(
    RUNTIME_LOG,
    encoding="utf-8"
)

runtime_handler.setLevel(logging.INFO)

runtime_handler.setFormatter(formatter)

# =====================================================
# ERROR HANDLER
# =====================================================

error_handler = logging.FileHandler(
    ERROR_LOG,
    encoding="utf-8"
)

error_handler.setLevel(logging.ERROR)

error_handler.setFormatter(formatter)

# =====================================================
# CONSOLE HANDLER
# =====================================================

console_handler = logging.StreamHandler()

console_handler.setLevel(logging.INFO)

console_handler.setFormatter(formatter)

# =====================================================
# ATTACH
# =====================================================

if not logger.handlers:

    logger.addHandler(runtime_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

# =====================================================
# HELPERS
# =====================================================

def log_info(message):

    logger.info(message)

def log_error(message):

    logger.error(message)

def log_exception(exc):

    logger.exception(exc)

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    log_info("Logger online")

    print("Logger test complete")
