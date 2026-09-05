"""Read-only health snapshot for the local GDP deployment."""

from __future__ import annotations

import os
import json
import math
import socket
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


GDP_SERVICE_UNIT = "gdp-server.service"
MQTT_SERVICE_UNIT = "autoirrigation-mqtt.service"
SYSTEMCTL = "/usr/bin/systemctl"
DEFAULT_DEVICE_STATE_FILE = "/run/gdp-server/devices.json"
MAX_DEVICE_STATE_BYTES = 1_048_576


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

    checked_at = datetime.now(timezone.utc)
    gdp_service = _systemd_unit_status(GDP_SERVICE_UNIT, runner)
    mqtt_service = _systemd_unit_status(MQTT_SERVICE_UNIT, runner)
    broker = _broker_status(host, port, connector)
    try:
        stale_after = int(environment.get("GDP_DEVICE_STALE_SECONDS", "90"))
        if not 10 <= stale_after <= 3600:
            raise ValueError
    except (TypeError, ValueError):
        stale_after = 90
    device_snapshot = _read_device_snapshot(
        environment.get("GDP_STATUS_FILE", DEFAULT_DEVICE_STATE_FILE),
        checked_at,
        stale_after,
    )
    healthy = gdp_service["active"] and mqtt_service["active"] and broker["reachable"]

    return {
        "healthy": healthy,
        "checked_at": checked_at.isoformat(),
        "gdp_server": gdp_service,
        "mqtt_service": mqtt_service,
        "broker": broker,
        "device_snapshot": device_snapshot,
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


def _read_device_snapshot(path_value, checked_at, stale_after):
    path = Path(path_value)
    try:
        raw_payload = path.read_bytes()
        if len(raw_payload) > MAX_DEVICE_STATE_BYTES:
            raise ValueError("device snapshot exceeds size limit")
        payload = json.loads(raw_payload)
        if not isinstance(payload, dict):
            raise ValueError("invalid device snapshot root")
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported device snapshot version")
        raw_devices = payload.get("devices")
        if not isinstance(raw_devices, dict):
            raise ValueError("invalid devices object")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "updated_at": None,
            "online_count": 0,
            "devices": [],
            "error": str(exc)[:160],
        }

    devices = []
    for device_id, raw in list(sorted(raw_devices.items()))[:64]:
        if not isinstance(device_id, str) or not isinstance(raw, dict):
            continue
        last_seen = _parse_timestamp(raw.get("last_seen"))
        age_seconds = (
            max(0, int((checked_at - last_seen).total_seconds()))
            if last_seen is not None
            else None
        )
        online = (
            age_seconds is not None
            and age_seconds <= stale_after
            and raw.get("reported_online") is not False
        )
        telemetry = raw.get("telemetry")
        state = raw.get("state")
        capabilities = raw.get("capabilities")
        last_message = raw.get("last_message")
        devices.append(
            {
                "device_id": device_id[:64],
                "online": online,
                "reported_online": raw.get("reported_online"),
                "last_seen": last_seen.isoformat() if last_seen else None,
                "age_seconds": age_seconds,
                "health": _safe_text(raw.get("health"), 64),
                "device_type": _safe_text(raw.get("device_type"), 64),
                "firmware_version": _safe_text(
                    raw.get("firmware_version"), 64
                ),
                "hardware_version": _safe_text(
                    raw.get("hardware_version"), 64
                ),
                "status_message": _safe_text(raw.get("status_message"), 160),
                "uptime_ms": _safe_nonnegative_int(raw.get("uptime_ms")),
                "free_heap_bytes": _safe_nonnegative_int(
                    raw.get("free_heap_bytes")
                ),
                "last_message": _safe_last_message(last_message),
                "capabilities": [
                    item[:96]
                    for item in capabilities[:16]
                    if isinstance(item, str)
                ]
                if isinstance(capabilities, list)
                else [],
                "telemetry": _safe_mapping(telemetry),
                "state": _safe_mapping(state),
            }
        )

    return {
        "available": True,
        "updated_at": _safe_text(payload.get("updated_at"), 64),
        "online_count": sum(device["online"] for device in devices),
        "devices": devices,
        "error": None,
    }


def _parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_text(value, limit):
    return value[:limit] if isinstance(value, str) else None


def _safe_nonnegative_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return min(value, 9_007_199_254_740_991)


def _safe_last_message(value):
    if not isinstance(value, dict):
        return {}
    message_id = value.get("message_id")
    return {
        # A uint64 cannot be represented exactly by JavaScript. Keep the ID as text.
        "message_id": (
            str(message_id)
            if isinstance(message_id, int)
            and not isinstance(message_id, bool)
            and message_id >= 0
            else None
        ),
        "category": _safe_text(value.get("category"), 64),
        "domain_id": _safe_nonnegative_int(value.get("domain_id")),
        "domain_version": _safe_nonnegative_int(value.get("domain_version")),
        "message_type": _safe_nonnegative_int(value.get("message_type")),
    }


def _safe_mapping(value):
    if not isinstance(value, dict):
        return {}
    sanitized = {}
    for key, item in list(value.items())[:16]:
        if not isinstance(key, str):
            continue
        if isinstance(item, bool) or item is None:
            sanitized[key[:64]] = item
        elif isinstance(item, (int, float)) and math.isfinite(item):
            sanitized[key[:64]] = item
        elif isinstance(item, str):
            sanitized[key[:64]] = item[:96]
    return sanitized
