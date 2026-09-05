"""Authenticated read-only service health routes."""

from flask import jsonify

from auth import token_required
from utils.service_status import get_gdp_stack_status


def register_service_routes(app):
    @app.route("/api/services/gdp", methods=["GET"])
    @token_required
    def gdp_service_status(user):
        return jsonify(get_gdp_stack_status())

    @app.route("/api/services/gdp/devices/<device_id>", methods=["GET"])
    @token_required
    def gdp_device_status(_user, device_id):
        status = get_gdp_stack_status()
        devices = status.get("device_snapshot", {}).get("devices", [])
        device = next(
            (item for item in devices if item.get("device_id") == device_id),
            None,
        )
        if device is None:
            return jsonify({"error": "device_not_found"}), 404
        return jsonify(
            {
                "checked_at": status.get("checked_at"),
                "healthy": status.get("healthy", False),
                "gdp_server": status.get("gdp_server", {}),
                "mqtt_service": status.get("mqtt_service", {}),
                "broker": status.get("broker", {}),
                "snapshot_updated_at": status.get("device_snapshot", {}).get(
                    "updated_at"
                ),
                "device": device,
            }
        )
