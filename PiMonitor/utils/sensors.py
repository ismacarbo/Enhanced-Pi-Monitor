"""Host sensor readers and the optional serial fan controller."""

import logging
import subprocess
import threading
import time

import serial


LOGGER = logging.getLogger(__name__)

def get_voltage():
    """Return the measured input voltage, or ``None`` when no ADC is present."""
    try:
        import Adafruit_ADS1x15

        adc = Adafruit_ADS1x15.ADS1115()
        val = adc.read_adc(0, gain=1)
        voltage = val * (4.096 / 32767) * 2
        return round(voltage, 2)
    except Exception as exc:  # Hardware drivers expose inconsistent errors.
        LOGGER.debug("voltage sensor unavailable: %s", exc)
        return None

def get_temp_c():
    """Read Raspberry Pi CPU temperature in °C, or ``None`` if unavailable."""
    try:
        out = subprocess.check_output(
            ["/usr/bin/vcgencmd", "measure_temp"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode()
        return float(out.split("=")[1].split("'")[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        try:
            with open(
                "/sys/class/thermal/thermal_zone0/temp", "r", encoding="ascii"
            ) as source:
                return float(source.read().strip()) / 1000.0
        except (OSError, ValueError):
            return None

def _fan_loop(port: str, baud: int, temp_on: float, temp_off: float):
    while True:
        try:
            LOGGER.info("opening fan serial controller on %s", port)
            with serial.Serial(port, baud, timeout=1) as ser:
                LOGGER.info("fan serial controller connected")
                fan_on = False
                while True:
                    t = get_temp_c()
                    if t is None:
                        time.sleep(5)
                        continue
                    if t >= temp_on and not fan_on:
                        ser.write(b"ON 200\n")
                        fan_on = True
                        LOGGER.info("fan enabled at %.1f °C", t)
                    elif t < temp_off and fan_on:
                        ser.write(b"OFF\n")
                        fan_on = False
                        LOGGER.info("fan disabled at %.1f °C", t)
                    time.sleep(2)
        except (OSError, serial.SerialException) as exc:
            LOGGER.warning("fan serial unavailable (%s); retrying in 15s", exc)
            time.sleep(15)

def start_fan_thread(port="/dev/ttyACM0", baud=115200, temp_on=50.0, temp_off=45.0):
    th = threading.Thread(target=_fan_loop, args=(port, baud, temp_on, temp_off), daemon=True)
    th.start()
    return th
