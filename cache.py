"""
Simple in-memory, thread-safe caches:
 - one slot for the IOP GPS login token (shared across all requests)
 - one dict for live/playback stream URLs, keyed by (imei, start_time, end_time)

Notes:
 - This is process-local. If the Flask app is ever run with multiple
   worker processes (e.g. gunicorn -w 2+) or multiple instances behind
   a load balancer, each process gets its own copy of these caches -
   fine for correctness (each will just log in / fetch independently
   the first time), but not shared. Move to Redis if that matters later.
 - Expiry is "lazy": we don't run a background cleanup job, we just
   check the timestamp whenever an entry is read.
"""
import threading
import time

_lock = threading.Lock()

_token_cache = {
    "token": None,
    "expires_at": 0.0,
}

_stream_cache = {}  # key -> {"data": ..., "expires_at": float}


# ---------------------------------------------------------------------------
# Login token cache
# ---------------------------------------------------------------------------

def get_cached_token():
    """Return the cached token if it exists and hasn't expired, else None."""
    with _lock:
        if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
            return _token_cache["token"]
        return None


def set_cached_token(token: str, ttl_seconds: float):
    with _lock:
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + ttl_seconds


# ---------------------------------------------------------------------------
# Live/playback stream URL cache
# ---------------------------------------------------------------------------

def make_stream_key(imei: str, channel: int) -> str:
    return f"{imei}:{channel}"


def get_cached_stream(key: str):
    """Return the cached stream response if fresh, else None."""
    with _lock:
        entry = _stream_cache.get(key)
        if entry and time.time() < entry["expires_at"]:
            return entry["data"]
        if entry:
            # stale - drop it so the cache doesn't grow forever
            del _stream_cache[key]
        return None


def set_cached_stream(key: str, data, ttl_seconds: float):
    with _lock:
        _stream_cache[key] = {
            "data": data,
            "expires_at": time.time() + ttl_seconds,
        }
