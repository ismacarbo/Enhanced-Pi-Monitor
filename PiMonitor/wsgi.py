"""Production WSGI entry point with one background hardware worker."""

import os

from app import app
from utils.sensors import start_fan_thread


if os.environ.get("PIMONITOR_START_FAN", "true").lower() not in {
    "0",
    "false",
    "no",
}:
    start_fan_thread(
        port=os.environ.get("PIMONITOR_FAN_PORT", "/dev/ttyACM0"),
        baud=int(os.environ.get("PIMONITOR_FAN_BAUD", "115200")),
        temp_on=float(os.environ.get("PIMONITOR_FAN_TEMP_ON", "50")),
        temp_off=float(os.environ.get("PIMONITOR_FAN_TEMP_OFF", "45")),
    )
