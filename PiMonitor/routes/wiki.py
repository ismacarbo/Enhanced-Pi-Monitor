"""Authenticated launcher route for the optional Wiki.js service."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import jwt
from flask import abort, request, redirect

from auth import token_required

WIKI_ACCESS_COOKIE = "pimonitor_wiki_access"


def register_wiki_routes(app):
    """Register the authenticated Wiki.js launcher endpoint."""

    @app.route("/wiki")
    @token_required
    def wiki(user):
        wikijs_url = app.config.get("WIKIJS_URL")
        if not wikijs_url:
            abort(503, description="Wiki.js is not configured")

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=app.config.get("WIKIJS_AUTH_TTL_SECONDS", 1800)
        )
        access_token = jwt.encode(
            {
                "username": user,
                "scope": "wikijs",
                "exp": expires_at,
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        response = redirect(wikijs_url)
        response.set_cookie(
            WIKI_ACCESS_COOKIE,
            access_token,
            max_age=app.config.get("WIKIJS_AUTH_TTL_SECONDS", 1800),
            secure=urlsplit(wikijs_url).scheme == "https",
            httponly=True,
            samesite="Lax",
            domain=app.config.get("WIKIJS_AUTH_COOKIE_DOMAIN"),
        )
        return response

    @app.route("/internal/auth/wiki")
    def wiki_auth():
        """Validate the short-lived cookie used by nginx ``auth_request``."""

        access_token = request.cookies.get(WIKI_ACCESS_COOKIE)
        if not access_token:
            return "", 401
        try:
            payload = jwt.decode(
                access_token,
                app.config["SECRET_KEY"],
                algorithms=["HS256"],
            )
        except jwt.InvalidTokenError:
            return "", 401
        if payload.get("scope") != "wikijs" or not payload.get("username"):
            return "", 401
        return "", 204
