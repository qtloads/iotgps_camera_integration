import os

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current working directory (no-op if absent)


def _get_bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


def _get_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ---- IOP GPS API settings ----
IOPGPS_DOMAIN = os.getenv("IOPGPS_DOMAIN", "https://open.iopgps.com/")
IOPGPS_APP_ID = os.getenv("IOPGPS_APP_ID")
IOPGPS_SECRET_KEY = os.getenv("IOPGPS_SECRET_KEY")

if not IOPGPS_APP_ID or not IOPGPS_SECRET_KEY:
    raise RuntimeError(
        "IOPGPS_APP_ID and IOPGPS_SECRET_KEY must be set (check your .env file)."
    )

_raw_keys = os.getenv("API_ACCESS_KEYS", "")
VALID_ACCESS_KEYS = {k.strip() for k in _raw_keys.split(",") if k.strip()}

# ---- Misc defaults for the dashcam operation call ----
DEFAULT_CHANNEL = os.getenv("DEFAULT_CHANNEL", "1")
DEFAULT_STREAM_PROTOCOL = os.getenv("DEFAULT_STREAM_PROTOCOL", "http")
REQUEST_TIMEOUT = _get_int("REQUEST_TIMEOUT", 15)  # seconds, outbound HTTP calls

_TOKEN_TTL_BUFFER_SECONDS = _get_int("TOKEN_TTL_BUFFER_SECONDS", 120)
TOKEN_TTL_SECONDS = 2 * 60 * 60 - _TOKEN_TTL_BUFFER_SECONDS
STREAM_URL_TTL_SECONDS = _get_int("STREAM_URL_TTL_SECONDS", 2 * 60 * 60)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "dashcam_service")
TOKEN_COLLECTION = os.getenv("MONGO_TOKEN_COLLECTION", "iopgps_tokens")
LOG_COLLECTION = os.getenv("MONGO_LOG_COLLECTION", "api_call_logs")
