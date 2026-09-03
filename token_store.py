"""
Persists the IOP GPS login token in MongoDB, keyed by a fixed document id
since there is only ever one active token for this app's appid.

Storing it in Mongo (rather than plain in-memory) means:
 - the token survives an app restart
 - it's shared across multiple worker processes/instances, so they don't
   each independently log in and burn through auth calls
"""
import time

import db

_TOKEN_DOC_ID = "iopgps_token"


def get_cached_token():
    """Return the stored token if it exists and hasn't expired, else None."""
    doc = db.tokens_collection.find_one({"_id": _TOKEN_DOC_ID})
    if doc and doc.get("expires_at", 0) > time.time():
        return doc["token"]
    return None


def set_cached_token(token: str, ttl_seconds: float):
    expires_at = time.time() + ttl_seconds
    db.tokens_collection.update_one(
        {"_id": _TOKEN_DOC_ID},
        {"$set": {
            "token": token,
            "expires_at": expires_at,
            "updated_at": time.time(),
        }},
        upsert=True,
    )
