"""Browser routes and authenticated session lifecycle."""

from __future__ import annotations

import hmac

from flask import Response, abort, redirect, render_template, request, session, url_for

import config
from auth import (
    clear_login_failures,
    csrf_token,
    login_is_throttled,
    record_login_failure,
    token_required,
    valid_csrf_token,
)


def register_core_routes(app):
    @app.route("/")
    def home():
        return redirect(url_for("portfolio"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("username"):
            return redirect(url_for("dashboard"))

        error = None
        status = 200
        if request.method == "POST":
            if not valid_csrf_token():
                abort(400, description="Invalid or expired form token")

            client_key = request.remote_addr or "unknown"
            if login_is_throttled(client_key):
                response = render_template(
                    "login.html",
                    error="Troppi tentativi. Riprova tra qualche minuto.",
                    csrf_token=csrf_token(),
                )
                return response, 429, {"Retry-After": "300"}

            username = request.form.get("username", "")
            password = request.form.get("password", "")
            expected_username = getattr(config, "USERNAME", "ismacarbo")
            if hmac.compare_digest(username, expected_username) and hmac.compare_digest(
                password, config.PASSWORD
            ):
                clear_login_failures(client_key)
                destination = _safe_next(request.form.get("next"))
                session.clear()
                session["username"] = expected_username
                session.permanent = True
                return redirect(destination or url_for("dashboard"))

            record_login_failure(client_key)
            error = "Credenziali non valide."
            status = 401

        return (
            render_template(
                "login.html",
                error=error,
                csrf_token=csrf_token(),
                next_url=_safe_next(request.args.get("next")),
            ),
            status,
        )

    @app.post("/logout")
    @token_required
    def logout(user):
        if not valid_csrf_token():
            abort(400, description="Invalid or expired form token")
        session.clear()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @token_required
    def dashboard(user):
        return render_template(
            "dashboard.html", username=user, csrf_token=csrf_token()
        )

    @app.route("/weather")
    @token_required
    def weather(user):
        return render_template(
            "weather.html",
            openweather_key=config.OPENWEATHER_API,
            windy_key=config.WINDY_API,
        )

    @app.route("/portfolio")
    def portfolio():
        return render_template("portfolio.html")

    @app.route("/projects")
    def projects():
        return render_template("projects.html")

    @app.route("/video_feed")
    @token_required
    def video_feed(user):
        from stream.mjpeg import gen_frames

        return Response(
            gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    @app.route("/objects")
    @token_required
    def objects(user):
        return render_template(
            "objects.html", username=user, csrf_token=csrf_token()
        )

    @app.route("/stream_face")
    @token_required
    def stream_face(user):
        return redirect(url_for("objects"))

    @app.route("/projects/robot")
    def project_robot():
        return render_template("projects/projectRobot.html")

    @app.route("/projects/iot")
    def project_iot():
        return render_template("projects/projectsIot.html")

    @app.route("/projects/machine_learning")
    def project_ml():
        return render_template("projects/projectsML.html")


def _safe_next(value):
    if isinstance(value, str) and value.startswith("/") and not value.startswith("//"):
        return value
    return None
