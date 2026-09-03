"""Session, CSRF, device-token, and login throttling helpers."""

from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, redirect, request, session, url_for

import config


LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 5
_login_failures = defaultdict(deque)
_login_lock = threading.Lock()


def token_required(function):
    """Require the signed Flask session and preserve API response semantics."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        user = session.get("username")
        if not isinstance(user, str) or not user:
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication_required"}), 401
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return function(user, *args, **kwargs)

    return wrapped


def device_token_required(function):
    """Authenticate non-browser legacy device ingestion endpoints."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        expected = (
            getattr(config, "DEVICE_API_TOKEN", "")
            or os.environ.get("PIMONITOR_DEVICE_TOKEN", "")
        )
        if not isinstance(expected, str) or not expected:
            return jsonify({"error": "device_api_not_configured"}), 503

        provided = request.headers.get("X-Device-Token", "")
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            provided = authorization[7:]
        if not provided or not hmac.compare_digest(provided, expected):
            return jsonify({"error": "invalid_device_token"}), 401
        return function(*args, **kwargs)

    return wrapped


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_csrf_token() -> bool:
    expected = session.get("csrf_token", "")
    provided = request.form.get("csrf_token", "") or request.headers.get(
        "X-CSRF-Token", ""
    )
    return bool(
        isinstance(expected, str)
        and isinstance(provided, str)
        and expected
        and provided
        and hmac.compare_digest(expected, provided)
    )


def login_is_throttled(client_key: str, now: float | None = None) -> bool:
    current = time.monotonic() if now is None else now
    with _login_lock:
        failures = _login_failures[client_key]
        _discard_expired(failures, current)
        return len(failures) >= LOGIN_MAX_FAILURES


def record_login_failure(client_key: str, now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    with _login_lock:
        failures = _login_failures[client_key]
        _discard_expired(failures, current)
        failures.append(current)


def clear_login_failures(client_key: str) -> None:
    with _login_lock:
        _login_failures.pop(client_key, None)


def _discard_expired(failures, now: float) -> None:
    threshold = now - LOGIN_WINDOW_SECONDS
    while failures and failures[0] < threshold:
        failures.popleft()
