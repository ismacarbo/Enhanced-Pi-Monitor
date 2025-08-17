from flask import Flask
from config import SECRET_KEY
from routes.core import register_core_routes
from routes.api import register_api_routes
from utils.sensors import start_fan_thread

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.url_map.strict_slashes = False

    
    register_core_routes(app)
    register_api_routes(app)

    return app

app = create_app()

if __name__ == "__main__":
    
    
    start_fan_thread(port="/dev/ttyACM0", baud=115200, temp_on=50.0, temp_off=45.0)

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
