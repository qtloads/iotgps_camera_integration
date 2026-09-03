from datetime import datetime, timezone

from flask import Flask, jsonify, request

import config
from iopgps_service import IopgpsError, get_cached_stream_data
from log_store import log_api_call

app = Flask(__name__)

@app.route("/api/live-stream", methods=["POST"])
def live_stream():
    body = request.get_json(silent=True) or {}
    request_time = datetime.now(timezone.utc)

    accesskey = body.get("accesskey")
    imei = body.get("imei")
    channel = body.get("channel")
    ip_address = request.remote_addr

    def _respond(success, status_code, message=None, cache_hit=None, data=None):
        response_body = {"success": success}
        if success:
            response_body.update({"url": data})
        response_body.update({"imei": imei, "message": message})

        log_api_call(
            imei=imei,
            type = "live-stream",
            start_date="",
            end_date="",
            accesskey=accesskey,
            ip_address=ip_address,
            cache_hit=cache_hit,
            success=success,
            status_code=status_code,
            request_body=body,
            response_body=response_body,
            request_time=request_time,
            response_time=datetime.now(timezone.utc),
            message=message,
        )
        return jsonify(response_body), status_code

    # ---- Authorize the caller against OUR API ----
    if not accesskey or accesskey not in config.VALID_ACCESS_KEYS:
        return _respond(False, 401, "Invalid or missing accesskey")

    # ---- Validate input ----
    if not imei:
        return _respond(False, 400, "imei is required")
    # ---- Validate input ----
    if not channel:
        return _respond(False, 400, "channel is required")
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        msg = "channel must be integers."
        return _respond(False, 400, msg)

    # ---- Get the stream data, reusing cached token/url where still valid ----
    try:
        stream_data, cache_hit = get_cached_stream_data(imei, channel)
    except IopgpsError as e:
        print(f"IopgpsError: {str(e)}")
        return _respond(False, 502, "API Error, Please contact us.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        return _respond(False, 500, "API Error, Please contact us.")
    if stream_data["success"]:
        url = stream_data["url"]
    else:
        url = ""
    return _respond(stream_data['success'], stream_data['code'], stream_data['message'], cache_hit=cache_hit, data=url)


@app.route("/api/playback", methods=["POST"])
def playback():
    body = request.get_json(silent=True) or {}
    request_time = datetime.now(timezone.utc)

    accesskey = body.get("accesskey")
    imei = body.get("imei")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    channel = body.get("channel")
    ip_address = request.remote_addr

    def _respond(success, status_code, message=None, cache_hit=None, data=None):
        response_body = {"success": success}
        if success:
            response_body.update({"imei": imei, "data": data})
        else:
            response_body["message"] = message

        log_api_call(
            imei=imei,
            type = "playback",
            start_date=start_date,
            end_date=end_date,
            accesskey=accesskey,
            ip_address=ip_address,
            cache_hit=cache_hit,
            success=success,
            status_code=status_code,
            request_body=body,
            response_body=response_body,
            request_time=request_time,
            response_time=datetime.now(timezone.utc),
            message=message,
        )
        return jsonify(response_body), status_code

    # ---- Authorize the caller against OUR API ----
    if not accesskey or accesskey not in config.VALID_ACCESS_KEYS:
        return _respond(False, 401, "Invalid or missing accesskey")

    # ---- Validate input ----
    if not imei:
        return _respond(False, 400, "imei is required")

    if not channel:
        return _respond(False, 400, "channel is required")


    try:
        start_time = int(start_date)
        end_time = int(end_date)
        channel = int(channel)
    except (TypeError, ValueError):
        msg = "start_date, end_date, and channel must be integers."
        return _respond(False, 400, msg)

    # ---- Get the stream data, reusing cached token/url where still valid ----
    try:
        stream_data, cache_hit = get_cached_stream_data(imei, start_time, end_time, channel)
    except IopgpsError as e:
        return _respond(False, 502, str(e))
    except Exception as e:
        return _respond(False, 500, f"Unexpected error: {e}")

    return _respond(True, 200, cache_hit=cache_hit, data=stream_data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
