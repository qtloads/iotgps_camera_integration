"""
Logs every call to /api/live-stream into MongoDB for audit/debugging purposes.
"""
from datetime import datetime, timezone
from flask import jsonify

import db

def log_api_call(*, imei, type, accesskey, ip_address,
                 cache_hit, success, request_body, response_body,
                 request_time, response_time):
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
        "accesskey_suffix": accesskey[-8:] if accesskey else None,
        "ip_address": ip_address,
        "cache_hit": cache_hit,
        "success": success
    }
    try:
        db.logs_collection.insert_one(doc)
    except Exception:
        pass


def respond(success, status_code, message, body, ip_address,request_time, type = "live-stream", cache_hit=None, data=None):
    response_body = {"success": success}
    if success:
        response_body.update({"url": data})
    response_body.update({"imei": body.get('imei', ''), "message": message})

    log_api_call(
        imei = body.get('imei', ''),
        type = type,
        accesskey = body.get('accesskey', ''),
        ip_address = ip_address,
        cache_hit = cache_hit,
        success = success,
        request_body = body,
        response_body = response_body,
        request_time = request_time,
        response_time = datetime.now(timezone.utc)
    )
    return jsonify(response_body), status_code