"""Authenticated dashboard APIs and token-authenticated device ingestion."""

from __future__ import annotations

import datetime
import math
import threading
import time

import psutil
from flask import Response, jsonify, redirect, render_template, request, url_for

from auth import (
    csrf_token,
    device_token_required,
    token_required,
    valid_csrf_token,
)
from occupancy.state import get_probability_map, update_from_points
from utils.names import sanitize_name
from utils.sensors import get_temp_c, get_voltage
from utils.telegram import send_telegram_alert


sensor_records = []
sensor_records_lock = threading.Lock()
MAX_RECORDS = 100
CPU_TEMP_THRESHOLD = 70.0
VOLTAGE_THRESHOLD = 4.8
ALERT_COOLDOWN_SECONDS = 900
last_alert_at = {}
alert_lock = threading.Lock()


def send_alert_with_cooldown(key, message):
    """Send a best-effort alert at most once per configured interval."""
    now = time.monotonic()
    with alert_lock:
        previous = last_alert_at.get(key, 0.0)
        if now - previous < ALERT_COOLDOWN_SECONDS:
            return
        last_alert_at[key] = now
    send_telegram_alert(message)


def register_api_routes(app):
    @app.get("/api/system")
    @token_required
    def system_info(_user):
        cpu_temp = get_temp_c()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        voltage = get_voltage()

        if cpu_temp is not None and cpu_temp > CPU_TEMP_THRESHOLD:
            send_alert_with_cooldown(
                "cpu_temperature", f"Alert: CPU temp high ({cpu_temp:.1f} °C)!"
            )
        if voltage is not None and voltage < VOLTAGE_THRESHOLD:
            send_alert_with_cooldown(
                "voltage", f"Alert: Low voltage ({voltage:.2f} V)!"
            )

        return jsonify(
            {
                "cpu_temperature": cpu_temp,
                "memory": {
                    "total": memory.total,
                    "used": memory.used,
                    "free": memory.free,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
                "voltage": voltage,
                "power_status": "Online",
            }
        )

    @app.get("/api/network")
    @token_required
    def network_info(_user):
        counters = psutil.net_io_counters(pernic=True)
        return jsonify(
            {
                interface: {
                    "bytes_sent": stats.bytes_sent,
                    "bytes_recv": stats.bytes_recv,
                    "packets_sent": stats.packets_sent,
                    "packets_recv": stats.packets_recv,
                }
                for interface, stats in counters.items()
            }
        )

    @app.get("/api/temperature")
    @device_token_required
    def temperature():
        try:
            temperature_value = float(request.args["temp"])
            humidity_value = float(request.args["hum"])
            if not math.isfinite(temperature_value) or not math.isfinite(
                humidity_value
            ):
                raise ValueError
            if not -50 <= temperature_value <= 100 or not 0 <= humidity_value <= 100:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return jsonify({"status": "error", "message": "Invalid values"}), 400

        app.logger.info(
            "legacy temperature received temp=%s hum=%s",
            temperature_value,
            humidity_value,
        )
        return jsonify(
            {
                "status": "success",
                "temperature": temperature_value,
                "humidity": humidity_value,
            }
        )

    @app.post("/api/face")
    @device_token_required
    def face_api():
        from detectors.yolo_face import register_face_from_upload

        data = request.get_data()
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        try:
            ok, message = register_face_from_upload(data, name="api")
        except (OSError, ValueError) as exc:
            app.logger.warning("invalid face upload: %s", exc)
            return jsonify({"status": "error", "message": "Invalid image"}), 400
        if ok:
            send_telegram_alert("Face registered from device API")
            return jsonify(
                {"status": "success", "message": "Registered", "recognition": "api"}
            )
        return jsonify({"status": "error", "message": message}), 400

    @app.get("/last_face.jpg")
    @token_required
    def last_face(_user):
        from detectors.yolo_face import get_last_face_jpg

        data = get_last_face_jpg()
        if not data:
            return "No face captured yet", 404
        return Response(data, mimetype="image/jpeg")

    @app.route("/register", methods=["GET", "POST"])
    @token_required
    def register(user):
        from detectors.yolo_face import register_face_from_last

        if request.method == "POST":
            if not valid_csrf_token():
                return "Invalid or expired form token", 400
            name = sanitize_name(request.form.get("name", ""))
            if not name:
                return "Missing name", 400
            ok, message = register_face_from_last(name)
            if not ok:
                return f"Error: {message}", 400
            return redirect(url_for("register_success", who=name))
        return render_template(
            "register.html", user=user, csrf_token=csrf_token()
        )

    @app.get("/register_success")
    @token_required
    def register_success(_user):
        who = sanitize_name(request.args.get("who", "")) or "utente"
        return render_template("register_success.html", who=who)

    @app.post("/api/register_face")
    @token_required
    def api_register_face(_user):
        from detectors.yolo_face import register_face_from_upload

        if not valid_csrf_token():
            return jsonify({"error": "invalid_csrf_token"}), 400
        name = sanitize_name(request.form.get("name", ""))
        uploaded_file = request.files.get("image")
        if not name or not uploaded_file:
            return jsonify(
                {"status": "error", "message": "name or image missing"}
            ), 400
        try:
            ok, message = register_face_from_upload(uploaded_file.read(), name)
        except (OSError, ValueError) as exc:
            app.logger.warning("invalid face upload: %s", exc)
            return jsonify({"status": "error", "message": "Invalid image"}), 400
        if ok:
            return jsonify({"status": "success", "name": name})
        return jsonify({"status": "error", "message": message}), 400

    @app.post("/api/irrigation_data")
    @device_token_required
    def add_irrigation_data():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"status": "error", "message": "Invalid payload"}), 400
        try:
            moisture = float(payload["moisture"])
            light = float(payload["light"])
            if not math.isfinite(moisture) or not math.isfinite(light):
                raise ValueError
            if not 0 <= moisture <= 100 or not 0 <= light <= 1_000_000:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return jsonify({"status": "error", "message": "Invalid payload"}), 400

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with sensor_records_lock:
            sensor_records.append(
                {"time": timestamp, "moisture": moisture, "light": light}
            )
            del sensor_records[:-MAX_RECORDS]
        if moisture < 50:
            send_alert_with_cooldown(
                "soil_moisture", f"Low moisture alert: {moisture:.1f}%"
            )
        return jsonify({"status": "success"}), 201

    @app.get("/api/irrigation_data")
    @token_required
    def get_irrigation_data(_user):
        with sensor_records_lock:
            return jsonify(list(sensor_records))

    @app.post("/api/lidarDatas")
    @device_token_required
    def lidar_data():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "invalid_payload"}), 400
        points = data.get("points", [])
        if not isinstance(points, list) or len(points) > 720:
            return jsonify({"error": "invalid_points"}), 400
        normalized_points = []
        try:
            for point in points:
                angle = float(point["angle"])
                distance = float(point["distance"])
                if not math.isfinite(angle) or not math.isfinite(distance):
                    raise ValueError
                if not -360 <= angle <= 360 or not 0 <= distance <= 1000:
                    raise ValueError
                normalized_points.append({"angle": angle, "distance": distance})
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid_points"}), 400
        update_from_points(normalized_points)
        return jsonify(
            {"status": "received", "point_count": len(normalized_points)}
        ), 201

    @app.get("/api/occupancy_map.json")
    @token_required
    def occupancy_map_json(_user):
        return jsonify(get_probability_map())
