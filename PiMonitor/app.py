import os
from datetime import timedelta

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from config import SECRET_KEY
from knowledge.sources.wikijs import WikiJSConfig, WikiJSConfigurationError
from routes.core import register_core_routes
from routes.api import register_api_routes
from routes.services import register_service_routes
from routes.wiki import register_wiki_routes
from utils.sensors import start_fan_thread

def create_app():
    if len(SECRET_KEY) < 32:
        raise RuntimeError("FLASK_SECRET_KEY must contain at least 32 characters")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=SECRET_KEY,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=256 * 1024,
        MAX_FORM_PARTS=20,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get(
            "PIMONITOR_COOKIE_SECURE", "true"
        ).lower()
        not in {"0", "false", "no"},
    )
    app.url_map.strict_slashes = False

    if os.environ.get("PIMONITOR_BEHIND_PROXY", "true").lower() not in {
        "0",
        "false",
        "no",
    }:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.config['WIKIJS_AUTH_COOKIE_DOMAIN'] = (
        os.environ.get('WIKIJS_AUTH_COOKIE_DOMAIN', '').strip() or None
    )
    try:
        wiki_auth_ttl = int(os.environ.get('WIKIJS_AUTH_TTL_SECONDS', '1800'))
        if wiki_auth_ttl <= 0:
            raise ValueError
    except ValueError:
        app.logger.warning(
            "Ignoring invalid WIKIJS_AUTH_TTL_SECONDS; using 1800 seconds"
        )
        wiki_auth_ttl = 1800
    app.config['WIKIJS_AUTH_TTL_SECONDS'] = wiki_auth_ttl

    try:
        app.config['WIKIJS_URL'] = WikiJSConfig.from_env().base_url
    except WikiJSConfigurationError as exc:
        app.logger.warning("Ignoring invalid optional Wiki.js configuration: %s", exc)
        app.config['WIKIJS_URL'] = None

    @app.context_processor
    def inject_optional_services():
        # Only the public base URL is exposed. WIKIJS_API_TOKEN remains backend-only.
        return {'wikijs_url': app.config.get('WIKIJS_URL')}

    register_core_routes(app)
    register_api_routes(app)
    register_service_routes(app)
    register_wiki_routes(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(self)"
        )
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.path.startswith("/api/") or request.path in {
            "/dashboard",
            "/login",
            "/objects",
            "/register",
            "/register_success",
            "/weather",
            "/video_feed",
            "/last_face.jpg",
        }:
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(413)
    def request_too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "request_too_large"}), 413
        return "Request too large", 413

    return app

app = create_app()

if __name__ == "__main__":
    start_fan_thread(port="/dev/ttyACM0", baud=115200, temp_on=50.0, temp_off=45.0)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
