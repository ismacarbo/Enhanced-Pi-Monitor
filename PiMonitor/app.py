import os

from flask import Flask
from config import SECRET_KEY
from knowledge.sources.wikijs import WikiJSConfig, WikiJSConfigurationError
from routes.core import register_core_routes
from routes.api import register_api_routes
from routes.services import register_service_routes
from routes.wiki import register_wiki_routes
from utils.sensors import start_fan_thread

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.url_map.strict_slashes = False

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

    return app

app = create_app()

if __name__ == "__main__":
    
    
    start_fan_thread(port="/dev/ttyACM0", baud=115200, temp_on=50.0, temp_off=45.0)

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
