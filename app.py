from datetime import datetime, timezone

from flask import Flask, request

import config
from iopgps_service import IopgpsError, get_cached_stream_data, get_playback_data
from log_store import respond

app = Flask(__name__)

@app.route("/api/live-stream", methods=["POST"])
def live_stream():
    body = request.get_json(silent=True) or {}
    request_time = datetime.now(timezone.utc)

    accesskey = body.get("accesskey")
    imei = body.get("imei")
    channel = body.get("channel")
    ip_address = request.remote_addr

    # ---- Authorize the caller against OUR API ----
    if not accesskey or accesskey not in config.VALID_ACCESS_KEYS:
        return respond(False, 401, "Invalid or missing accesskey", body, ip_address,request_time)

    # ---- Validate input ----
    if not imei:
        return respond(False, 400, "imei is required", body, ip_address,request_time)
    # ---- Validate input ----
    if not channel:
        return respond(False, 400, "channel is required", body, ip_address,request_time)
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        msg = "channel must be integers."
        return respond(False, 400, msg, body, ip_address,request_time)

    # ---- Get the stream data, reusing cached token/url where still valid ----
    try:
        stream_data, cache_hit = get_cached_stream_data(imei, channel)
    except IopgpsError as e:
        print(f"IopgpsError: {str(e)}")
        return respond(False, 502, "API Error, Please contact us.", body, ip_address,request_time)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return respond(False, 500, "API Error, Please contact us.", body, ip_address,request_time)
    if stream_data["success"]:
        url = stream_data["url"]
    else:
        url = ""
    return respond(stream_data['success'], stream_data['code'], stream_data['message'], body, ip_address,request_time, cache_hit=cache_hit, data=url)


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

    # ---- Authorize the caller against OUR API ----
    if not accesskey or accesskey not in config.VALID_ACCESS_KEYS:
        return respond(False, 401, "Invalid or missing accesskey", body, ip_address,request_time, "playback")

    # ---- Validate input ----
    if not imei:
        return respond(False, 400, "imei is required", body, ip_address,request_time, "playback")

    if not channel:
        return respond(False, 400, "channel is required", body, ip_address,request_time, "playback")

    try:
        start_time = int(start_date)
        end_time = int(end_date)
        channel = int(channel)
    except (TypeError, ValueError):
        msg = "start_date, end_date, and channel must be integers."
        return respond(False, 400, msg, body, ip_address,request_time, "playback")

    if end_time < start_time:
        return respond(False, 400, "end_date must be greater than or equal to start_date.", body, ip_address,request_time, "playback")

    if end_time - start_time > 10 * 60:
        return respond(False, 400, "Playback duration must not exceed 10 minutes.", body, ip_address,request_time, "playback")

    # ---- Get the stream data, reusing cached token/url where still valid ----
    try:
        stream_data, cache_hit = get_playback_data(imei, start_time, end_time, channel)
    except IopgpsError as e:
        print(f"IopgpsError: {str(e)}")
        return respond(False, 502, "API Error, Please contact us.", body, ip_address,request_time, "playback")
    except Exception as e:
        print(f"Unexpected error: {e}")
        return respond(False, 500, "API Error, Please contact us.", body, ip_address,request_time, "playback")
    # return _respond(True, 200, cache_hit=cache_hit, data=stream_data)
    if stream_data["success"]:
        url = stream_data["url"]
    else:
        url = ""
    return respond(stream_data['success'], stream_data['code'], stream_data['message'], body, ip_address,request_time, "playback" , cache_hit=cache_hit, data=url)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
