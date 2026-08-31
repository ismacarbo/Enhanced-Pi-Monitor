"""Tests for the protected GDP deployment status integration."""

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import jwt
from flask import Flask

PIMONITOR_ROOT = Path(__file__).resolve().parents[1]
if str(PIMONITOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PIMONITOR_ROOT))

TEST_SECRET = "wiki-route-test-secret-with-at-least-32-bytes"
config_module = types.ModuleType("config")
config_module.SECRET_KEY = TEST_SECRET
sys.modules.setdefault("config", config_module)

from routes.services import register_service_routes  # noqa: E402
from utils.service_status import get_gdp_stack_status  # noqa: E402


def systemctl_result(unit, *, active=True):
    main_pid = "4321" if active and unit == "gdp-server.service" else "0"
    state = "active" if active else "failed"
    sub_state = "running" if main_pid != "0" else ("exited" if active else "failed")
    return types.SimpleNamespace(
        returncode=0,
        stdout=(
            f"Id={unit}\n"
            f"Description={unit}\n"
            "LoadState=loaded\n"
            f"ActiveState={state}\n"
            f"SubState={sub_state}\n"
            f"MainPID={main_pid}\n"
            "ActiveEnterTimestamp=Tue 2026-09-01 10:00:00 CEST\n"
        ),
        stderr="",
    )


class ClosableSocket:
    def close(self):
        pass


class ServiceStatusTests(unittest.TestCase):
    def test_healthy_requires_both_units_and_reachable_broker(self):
        runner = Mock(side_effect=lambda args, **_kwargs: systemctl_result(args[2]))
        connector = Mock(return_value=ClosableSocket())

        status = get_gdp_stack_status(
            runner=runner,
            connector=connector,
            environ={"GDP_STATUS_MQTT_PORT": "1884"},
        )

        self.assertTrue(status["healthy"])
        self.assertEqual(status["gdp_server"]["main_pid"], 4321)
        self.assertTrue(status["broker"]["reachable"])
        connector.assert_called_once_with(("127.0.0.1", 1884), timeout=0.5)

    def test_unreachable_broker_marks_stack_degraded(self):
        runner = Mock(side_effect=lambda args, **_kwargs: systemctl_result(args[2]))
        connector = Mock(side_effect=ConnectionRefusedError("refused"))

        status = get_gdp_stack_status(runner=runner, connector=connector, environ={})

        self.assertFalse(status["healthy"])
        self.assertFalse(status["broker"]["reachable"])


class ServiceStatusRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY=TEST_SECRET)

        @self.app.route("/login")
        def login():
            return "login"

        register_service_routes(self.app)
        self.client = self.app.test_client()

    def authenticate(self):
        token = jwt.encode(
            {
                "username": "ismacarbo",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            TEST_SECRET,
            algorithm="HS256",
        )
        with self.client.session_transaction() as session:
            session["jwt"] = token

    def test_anonymous_status_request_redirects_to_login(self):
        response = self.client.get("/api/services/gdp")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    @patch("routes.services.get_gdp_stack_status")
    def test_authenticated_status_request_returns_json(self, get_status):
        get_status.return_value = {"healthy": True}
        self.authenticate()

        response = self.client.get("/api/services/gdp")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"healthy": True})


if __name__ == "__main__":
    unittest.main()
