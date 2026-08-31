"""Authenticated read-only service health routes."""

from flask import jsonify

from auth import token_required
from utils.service_status import get_gdp_stack_status


def register_service_routes(app):
    @app.route("/api/services/gdp", methods=["GET"])
    @token_required
    def gdp_service_status(user):
        return jsonify(get_gdp_stack_status())
