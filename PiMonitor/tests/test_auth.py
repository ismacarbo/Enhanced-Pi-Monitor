"""Authentication boundary tests for browsers and embedded clients."""

import sys
import types
import unittest
from pathlib import Path

from flask import Flask, jsonify


PIMONITOR_ROOT = Path(__file__).resolve().parents[1]
if str(PIMONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PIMONITOR_ROOT))

config = sys.modules.setdefault("config", types.ModuleType("config"))
config.SECRET_KEY = "auth-test-secret-with-more-than-thirty-two-characters"
config.DEVICE_API_TOKEN = "device-test-token"
config.USERNAME = "ismacarbo"
config.PASSWORD = "correct horse battery staple"
config.OPENWEATHER_API = ""
config.WINDY_API = ""

from auth import device_token_required, token_required  # noqa: E402
from routes.core import register_core_routes  # noqa: E402


class AuthenticationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY=config.SECRET_KEY)

        @self.app.get("/login")
        def login():
            return "login"

        @self.app.get("/private-page")
        @token_required
        def private_page(user):
            return user

        @self.app.get("/api/private")
        @token_required
        def private_api(user):
            return jsonify({"user": user})

        @self.app.post("/api/device")
        @device_token_required
        def device_api():
            return jsonify({"accepted": True})

        self.client = self.app.test_client()

    def test_browser_page_redirects_to_login(self):
        response = self.client.get("/private-page")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=", response.headers["Location"])

    def test_api_returns_401_instead_of_html_redirect(self):
        response = self.client.get("/api/private")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "authentication_required"})

    def test_session_authenticates_browser_api(self):
        with self.client.session_transaction() as session:
            session["username"] = "ismacarbo"
        response = self.client.get("/api/private")
        self.assertEqual(response.get_json(), {"user": "ismacarbo"})

    def test_device_endpoint_requires_constant_time_token_boundary(self):
        self.assertEqual(self.client.post("/api/device").status_code, 401)
        response = self.client.post(
            "/api/device", headers={"X-Device-Token": "device-test-token"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"accepted": True})


class LoginLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__, template_folder=str(PIMONITOR_ROOT / "templates")
        )
        self.app.config.update(TESTING=True, SECRET_KEY=config.SECRET_KEY)
        register_core_routes(self.app)
        self.client = self.app.test_client()

    def test_login_requires_csrf_and_creates_session(self):
        self.assertEqual(
            self.client.post(
                "/login",
                data={"username": config.USERNAME, "password": config.PASSWORD},
            ).status_code,
            400,
        )
        self.client.get("/login")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        response = self.client.post(
            "/login",
            data={
                "username": config.USERNAME,
                "password": config.PASSWORD,
                "csrf_token": token,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))
        with self.client.session_transaction() as session:
            self.assertEqual(session["username"], config.USERNAME)


if __name__ == "__main__":
    unittest.main()
