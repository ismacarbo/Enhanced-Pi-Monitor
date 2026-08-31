"""Read-only health snapshot for the local GDP deployment."""

from __future__ import annotations

import os
import socket
import subprocess
from contextlib import closing
from datetime import datetime, timezone


GDP_SERVICE_UNIT = "gdp-server.service"
MQTT_SERVICE_UNIT = "autoirrigation-mqtt.service"
SYSTEMCTL = "/usr/bin/systemctl"


def get_gdp_stack_status(
    *,
    runner=subprocess.run,
    connector=socket.create_connection,
    environ=None,
):
    """Return systemd and broker health without exposing service controls."""
    environment = os.environ if environ is None else environ
    host = environment.get("GDP_STATUS_MQTT_HOST", "127.0.0.1")
    try:
        port = int(environment.get("GDP_STATUS_MQTT_PORT", "1883"))
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        port = 1883

    gdp_service = _systemd_unit_status(GDP_SERVICE_UNIT, runner)
    mqtt_service = _systemd_unit_status(MQTT_SERVICE_UNIT, runner)
    broker = _broker_status(host, port, connector)
    healthy = gdp_service["active"] and mqtt_service["active"] and broker["reachable"]

    return {
        "healthy": healthy,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "gdp_server": gdp_service,
        "mqtt_service": mqtt_service,
        "broker": broker,
    }


def _systemd_unit_status(unit, runner):
    command = [
        SYSTEMCTL,
        "show",
        unit,
        "--no-pager",
        "--property=Id,Description,LoadState,ActiveState,SubState,MainPID,ActiveEnterTimestamp",
    ]
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _unavailable_unit(unit, str(exc))

    properties = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key] = value

    if result.returncode != 0 or properties.get("LoadState") != "loaded":
        detail = result.stderr.strip() or "unit not loaded"
        return _unavailable_unit(unit, detail)

    return {
        "unit": unit,
        "description": properties.get("Description") or unit,
        "loaded": True,
        "active": properties.get("ActiveState") == "active",
        "active_state": properties.get("ActiveState") or "unknown",
        "sub_state": properties.get("SubState") or "unknown",
        "main_pid": _safe_int(properties.get("MainPID")),
        "active_since": properties.get("ActiveEnterTimestamp") or None,
        "error": None,
    }


def _unavailable_unit(unit, detail):
    return {
        "unit": unit,
        "description": unit,
        "loaded": False,
        "active": False,
        "active_state": "unavailable",
        "sub_state": "unknown",
        "main_pid": 0,
        "active_since": None,
        "error": detail[:160],
    }


def _broker_status(host, port, connector):
    try:
        with closing(connector((host, port), timeout=0.5)):
            pass
    except OSError as exc:
        return {
            "host": host,
            "port": port,
            "reachable": False,
            "error": str(exc)[:160],
        }
    return {"host": host, "port": port, "reachable": True, "error": None}


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
