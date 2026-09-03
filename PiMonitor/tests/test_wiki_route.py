"""Tests for the authenticated Wiki.js launcher route."""

import sys
import types
import unittest
from pathlib import Path

import jwt
from flask import Flask

PIMONITOR_ROOT = Path(__file__).resolve().parents[1]
if str(PIMONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PIMONITOR_ROOT))

TEST_SECRET = "wiki-route-test-secret-with-at-least-32-bytes"
config_module = types.ModuleType("config")
config_module.SECRET_KEY = TEST_SECRET
sys.modules.setdefault("config", config_module)

from routes.wiki import register_wiki_routes  # noqa: E402


class WikiRouteTests(unittest.TestCase):
    """Verify authentication and configuration behavior for ``/wiki``."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY=TEST_SECRET,
            WIKIJS_URL="https://wiki.example.invalid",
            WIKIJS_AUTH_COOKIE_DOMAIN=None,
            WIKIJS_AUTH_TTL_SECONDS=300,
        )

        @self.app.route("/login")
        def login():
            return "login"

        register_wiki_routes(self.app)
        self.client = self.app.test_client()

    def authenticate(self):
        with self.client.session_transaction() as session:
            session["username"] = "ismacarbo"

    def test_anonymous_request_redirects_to_login(self):
        response = self.client.get("/wiki")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=", response.headers["Location"])

    def test_authenticated_request_redirects_to_wikijs(self):
        self.authenticate()

        response = self.client.get("/wiki")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://wiki.example.invalid")
        cookie = response.headers["Set-Cookie"]
        self.assertIn("pimonitor_wiki_access=", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_nginx_auth_endpoint_requires_valid_launcher_cookie(self):
        self.assertEqual(self.client.get("/internal/auth/wiki").status_code, 401)
        self.authenticate()
        self.client.get("/wiki")

        response = self.client.get("/internal/auth/wiki")

        self.assertEqual(response.status_code, 204)

    def test_missing_configuration_returns_service_unavailable(self):
        self.app.config["WIKIJS_URL"] = None
        self.authenticate()

        response = self.client.get("/wiki")

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
