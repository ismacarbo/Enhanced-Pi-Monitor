"""Authenticated launcher route for the optional Wiki.js service."""

from flask import abort, redirect

from auth import token_required


def register_wiki_routes(app):
    """Register the authenticated Wiki.js launcher endpoint."""

    @app.route("/wiki")
    @token_required
    def wiki(user):
        del user  # Authentication is required even though the redirect needs no user data.
        wikijs_url = app.config.get("WIKIJS_URL")
        if not wikijs_url:
            abort(503, description="Wiki.js is not configured")
        return redirect(wikijs_url)
