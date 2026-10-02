#!/usr/bin/env python3
"""
Pulls telemetry from API 1 (Flespi) every 30 seconds and pushes the mapped
payload to API 2 (Tecdatum VTS).

Setup:
    pip install requests
    export FLESPI_TOKEN="your_flespi_token"
    python flespi_to_tecdatum.py

Optional environment variables:
    DEVICE_ID          Flespi device id               (default: 9117737)
    POLL_INTERVAL      Seconds between cycles          (default: 30)
    DISPLAY_TZ         "UTC" or "IST" for dateTime     (default: UTC)
    SKIP_DUPLICATES    "true" = don't re-push a record whose device
                       timestamp was already sent      (default: false)
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current working directory (no-op if absent)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
FLESPI_TOKEN = os.getenv("FLESPI_TOKEN")

DEVICE_ID = os.getenv("DEVICE_ID", "9117737")

API2_URL = os.getenv("API2_URL", "https://tecdatum.org/VTS/api/Tracking/VehicleDataRequest")

API1_URL = f"https://flespi.io/gw/devices/{DEVICE_ID}/telemetry/all"

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 2
SKIP_DUPLICATES = os.getenv("SKIP_DUPLICATES", "true").lower() == "true"

TZ_MAP = {
    "UTC": timezone.utc,
    "IST": timezone(timedelta(hours=5, minutes=30)),
}
DISPLAY_TZ = TZ_MAP.get(os.getenv("DISPLAY_TZ", "IST").upper(), timezone.utc)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("flespi-to-tecdatum")

_running = True


def _stop(signum, _frame):
    global _running
    log.info("Signal %s received, shutting down after current cycle...", signum)
    _running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def tel_value(telemetry: dict, key: str, default=None):
    """Safely read telemetry[key]['value']."""
    item = telemetry.get(key)
    if isinstance(item, dict):
        return item.get("value", default)
    return default


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """HTTP request with simple exponential backoff on failures."""
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            log.warning("%s %s failed (attempt %d/%d): %s",
                        method, url, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    raise last_exc


# --------------------------------------------------------------------------
# API 1 -> pull
# --------------------------------------------------------------------------
def fetch_api1() -> dict:
    resp = request_with_retry(
        "GET",
        API1_URL,
        headers={"Authorization": f"FlespiToken {FLESPI_TOKEN}"},
    )
    log.info("Flespi (HTTP %s) | response=%s",
                 resp.status_code, resp.text[:200])
    return resp.json()


# --------------------------------------------------------------------------
# Mapping API 1 -> API 2
# --------------------------------------------------------------------------
def map_to_api2(api1_response: dict) -> dict:
    result = api1_response.get("result") or []
    if not result:
        raise ValueError("API 1 returned an empty 'result' list")

    t = result[0].get("telemetry", {})

    # Epoch seconds -> "YYYY-MM-DD HH:MM:SS" (format used in API 2 sample)
    ts = tel_value(t, "timestamp")
    date_time = (
        datetime.fromtimestamp(float(ts), tz=DISPLAY_TZ).strftime("%Y-%m-%d %H:%M:%S")
        if ts is not None
        else ""
    )

    ignition = tel_value(t, "engine.ignition.status")
    gps_valid = tel_value(t, "position.valid")

    def s(v):  # API 2 sample sends every field as a string
        return "" if v is None else str(v)

    return {
        "imeiNo": s(tel_value(t, "ident")),
        "latitude": s(tel_value(t, "position.latitude")),
        "longitude": s(tel_value(t, "position.longitude")),
        "speed": s(tel_value(t, "position.speed")),
        "dateTime": date_time,
        "ignition": "on" if ignition else "off",
        "direction": s(tel_value(t, "position.direction")),
        "gpSstatus": "On" if gps_valid else "Off",
        "rawData": "NA",
    }


# --------------------------------------------------------------------------
# API 2 -> push
# --------------------------------------------------------------------------
def push_api2(payload: dict) -> requests.Response:
    return request_with_retry(
        "POST",
        API2_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
    )


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------
def run_cycle(state: dict) -> None:
    api1_data = fetch_api1()
    # Optional de-duplication based on the device timestamp
    if SKIP_DUPLICATES:
        ts = tel_value(api1_data["result"][0]["telemetry"], "timestamp")
        if ts is not None and ts == state.get("last_ts"):
            log.info("No new device data (timestamp %s) - skipping push", ts)
            return
        state["last_ts"] = ts

    payload = map_to_api2(api1_data)
    resp = push_api2(payload)
    log.info("Pushed OK (HTTP %s) payload=%s | response=%s",
             resp.status_code, json.dumps(payload), resp.text[:200])


def main() -> None:
    if not FLESPI_TOKEN:
        sys.exit("ERROR: set the FLESPI_TOKEN environment variable first.")

    log.info("Starting: device=%s interval=%ss tz=%s skip_duplicates=%s",
             DEVICE_ID, POLL_INTERVAL, DISPLAY_TZ, SKIP_DUPLICATES)
    # log.info(f"FLESPI TOKEN : {FLESPI_TOKEN}")
    state = {}
    next_run = time.monotonic()

    while _running:
        try:
            run_cycle(state)
        except Exception as exc:  # keep the service alive on any error
            log.error("Cycle failed: %s", exc, exc_info=True)

        # Fixed-rate scheduling: avoids drift from processing time
        next_run += POLL_INTERVAL
        sleep_for = next_run - time.monotonic()
        if sleep_for < 0:  # fell behind (e.g. long retries) - resync
            next_run = time.monotonic()
            sleep_for = 0
        # Sleep in small steps so Ctrl+C / SIGTERM is responsive
        end = time.monotonic() + sleep_for
        while _running and time.monotonic() < end:
            time.sleep(min(1, end - time.monotonic()))

    log.info("Stopped.")


# main()