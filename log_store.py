"""
Logs every call to /api/live-stream into MongoDB for audit/debugging purposes.
"""
from datetime import datetime, timezone

import db


def log_api_call(*, imei, type, start_date, end_date, accesskey, ip_address,
                 cache_hit, success, status_code, request_body, response_body,
                 request_time, response_time, message=None):
    """
    Insert one log document. Never raises - a logging failure should not
    break the API response, so any Mongo error is swallowed (and could be
    routed to stderr/monitoring instead if you want visibility on that).
    """
    doc = {
        # Kept for backwards compatibility with existing log consumers.
        "timestamp": datetime.now(timezone.utc),
        "request_time": request_time,
        "response_time": response_time,
        "request": request_body,
        "response": response_body,
        "imei": imei,
        "type" : type,
        "start_date": start_date,
        "end_date": end_date,
        # The complete inbound payload is persisted above as requested. Keep
        # this convenient, non-secret identifier for existing log queries.
        "accesskey_suffix": accesskey[-4:] if accesskey else None,
        "ip_address": ip_address,
        "cache_hit": cache_hit,
        "success": success,
        "status_code": status_code,
        "message": message,
    }
    try:
        db.logs_collection.insert_one(doc)
    except Exception:
        pass
