"""Smoke tests for the shared public-site presentation shell."""

import sys
import types
import unittest
from pathlib import Path

from flask import Flask


PIMONITOR_ROOT = Path(__file__).resolve().parents[1]
if str(PIMONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PIMONITOR_ROOT))

config = sys.modules.setdefault("config", types.ModuleType("config"))
config.SECRET_KEY = getattr(
    config, "SECRET_KEY", "public-ui-test-secret-with-more-than-thirty-two-characters"
)
config.USERNAME = getattr(config, "USERNAME", "ismacarbo")
config.PASSWORD = getattr(config, "PASSWORD", "test-password")
config.OPENWEATHER_API = getattr(config, "OPENWEATHER_API", "")
config.WINDY_API = getattr(config, "WINDY_API", "")

from routes.core import register_core_routes  # noqa: E402


class PublicPresentationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(PIMONITOR_ROOT / "templates"),
            static_folder=str(PIMONITOR_ROOT / "static"),
        )
        self.app.config.update(TESTING=True, SECRET_KEY=config.SECRET_KEY)
        register_core_routes(self.app)
        self.client = self.app.test_client()

    def test_public_pages_share_navigation_and_visual_assets(self):
        for path in (
            "/portfolio",
            "/projects",
            "/projects/robot",
            "/projects/iot",
            "/projects/machine_learning",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('class="site-header"', html)
                self.assertIn('id="main-content"', html)
                self.assertIn("css/styleStatic.css", html)
                self.assertIn("js/public.js", html)
                self.assertIn("Control center", html)
                self.assertIn(
                    f'<link rel="canonical" href="https://ismacarbo.org{path}">',
                    html,
                )

    def test_control_center_link_keeps_dashboard_protected(self):
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=", response.headers["Location"])

    def test_public_visual_assets_are_served(self):
        for path, content_type in (
            ("/static/css/styleStatic.css", "text/css"),
            ("/static/js/public.js", "text/javascript"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(content_type, response.content_type)
                    self.assertGreater(len(response.data), 100)
                finally:
                    response.close()


if __name__ == "__main__":
    unittest.main()
