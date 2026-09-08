import hashlib
import json
import time

import requests

import cache
import config
import token_store


class IopgpsError(Exception):
    """Raised when the IOP GPS API returns an error or an unexpected response."""
    pass

def _get_signature(secret_key: str, time_sec: int) -> str:
    md1 = hashlib.md5(secret_key.encode()).hexdigest()
    combined = md1 + str(time_sec)
    return hashlib.md5(combined.encode()).hexdigest()


def get_valid_token() -> str:
    cached = token_store.get_cached_token()
    if cached:
        return cached

    token = _login()
    token_store.set_cached_token(token, config.TOKEN_TTL_SECONDS)
    return token


def _login() -> str:
    """Authenticate against IOP GPS and return a fresh accessToken."""
    time_sec = int(time.time())
    url = config.IOPGPS_DOMAIN + "api/auth"
    payload = json.dumps({
        "appid": config.IOPGPS_APP_ID,
        "time": time_sec,
        "signature": _get_signature(config.IOPGPS_SECRET_KEY, time_sec),
    })
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers=headers, data=payload, timeout=config.REQUEST_TIMEOUT)

    try:
        data = response.json()
    except ValueError:
        raise IopgpsError(f"Non-JSON auth response from IOP GPS: {response.text}")

    token = data.get("accessToken")
    if not token:
        raise IopgpsError(f"Failed to obtain login token: {data}")
    return token

# process response, eject only url and channel

def processResponse(data):
    res = {}
    try:
        if data['code'] == 0:
            pp = {}
            res["success"] = True
            res["code"] = 200
            res["message"] = "URL generated!"
            pp["channel"] = data["data"][0]["channel"]
            pp["url"] = config.DEFAULT_STREAM_PROTOCOL + ":"+data["data"][0]["flvUrl"]
            res["url"] = pp
        elif data['code'] == 590003:
            res["success"] = False
            res["code"] = 500
            res["message"] = "API Error: Permission Denied, Please contact us!"
        else:
            res["success"] = False
            res["code"] = 500
            res["message"] = "API Error, Please contact us!" 
    except:
        res["success"] = False
        res["code"] = 500
        res["message"] = "Unexpected API Error, Please contact us!" 

    # print("res", res)
    return res



# live streaming functions

def get_cached_stream_data(imei: str, channel : int):
    key = cache.make_stream_key(imei, channel)

    cached = cache.get_cached_stream(key)
    if cached:
        return cached, True

    token = get_valid_token()
    data = _fetch_live_stream_url(token, imei, channel)
    resData = processResponse(data)
    cache.set_cached_stream(key, resData, config.STREAM_URL_TTL_SECONDS)
    return resData, False


def _fetch_live_stream_url(token: str, imei: str, channel : int) -> dict:
    url = config.IOPGPS_DOMAIN + "api/dashcam/operation"
    # print(token)
    payload = json.dumps([
        {
            "imei": imei,
            "channel": int(channel),
            "operatorType": "video.open",
            "startTime": "",
            "endTime": "",
            "streamProtocol": config.DEFAULT_STREAM_PROTOCOL,
        }
    ])
    headers = {
        "accessToken": token,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload, timeout=config.REQUEST_TIMEOUT)

    try:
        data = response.json()
    except ValueError:
        raise IopgpsError(f"Non-JSON stream response from IOP GPS: {response.text}")
    # print(data)
    return data


# playback streaming functions

def get_playback_data(imei: str, start_time: int, end_time: int, channel: int):
    token = get_valid_token()
    data = _fetch_playback_stream_url(token, imei, start_time, end_time, channel)
    resData = processResponse(data)
    return resData, False


def _fetch_playback_stream_url(token: str, imei: str, start_time: int, end_time: int, channel : int) -> dict:
    url = config.IOPGPS_DOMAIN + "api/dashcam/operation"
    # print(token)
    payload = json.dumps([
        {
            "imei": imei,
            "channel": int(channel),
            "operatorType": "replay.open",
            "startTime": start_time,
            "endTime": end_time,
            "streamProtocol": config.DEFAULT_STREAM_PROTOCOL,
        }
    ])
    headers = {
        "accessToken": token,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload, timeout=config.REQUEST_TIMEOUT)

    try:
        data = response.json()
    except ValueError:
        raise IopgpsError(f"Non-JSON stream response from IOP GPS: {response.text}")
    # print(data)
    return data

# get event functions

def get_event_list(imei: str, start_time: int, end_time: int, fileType):
    token = get_valid_token()
    data = _fetch_event_list_detail(token, imei, start_time, end_time)
    resData = processEventResponse(data, fileType)
    return resData, False


def _fetch_event_list_detail(token: str, imei: str, start_time: int, end_time: int) -> dict:
    url = config.IOPGPS_DOMAIN + "api/device/alarm"
    # print(token)
    params = {
        "imei": imei,
        "startTime": start_time,
        "endTime": end_time
    }
    headers = {
        "accessToken": token,
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, params=params, timeout=config.REQUEST_TIMEOUT)

    try:
        data = response.json()
    except ValueError:
        raise IopgpsError(f"Non-JSON stream response from IOP GPS: {response.text}")
    # print(data)
    return data

def processEventResponse(data,fileType):
    res = {}
    try:
        if data['code'] == 0:
            alertDataArray = []
            res["success"] = True
            res["code"] = 200
            res["message"] = "Events data found."
            alert = data["details"]
            for al in alert: 
                alertObj = {}
                alertObj["imei"] = al["imei"]
                alertObj["lat"] = al["lat"]
                alertObj["lng"] = al["lng"]
                alertObj["time"] = al["time"]
                alertObj["speed"] = al["speed"]
                alertObj["alarmCode"] = al["alarmCode"]
                alertObj["alarmType"] = al["alarmType"]
                if fileType == "image":
                    alertObj["url"] = getUrl(al["extData"]["images"])
                elif fileType == "video":
                    alertObj["url"] = getUrl(al["extData"]["mp4"])
                else:
                    alertObj["url"] = getUrl(al["extData"]["zip"])
                alertDataArray.append(alertObj)
            res["alertData"] = alertDataArray
        elif data['code'] == 590003:
            res["success"] = False
            res["code"] = 500
            res["message"] = "API Error: Permission Denied, Please contact us!"
        else:
            res["success"] = False
            res["code"] = 500
            res["message"] = "API Error, Please contact us!" 
    except Exception as err:
        print (err)
        res["success"] = False
        res["code"] = 500
        res["message"] = "Unexpected API Error, Please contact us!" 
    # print("res", res)
    return res

def getUrl(data):
    if isinstance(data, str):
        res = config.DEFAULT_STREAM_PROTOCOL + ":"+data
    elif isinstance(data, list):
        res = []
        for item in data:
            res.append(config.DEFAULT_STREAM_PROTOCOL + ":"+item)
    else:
        res = "Url not found"
    return res

