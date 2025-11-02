"""Authentication helpers for Conflagent endpoints."""

from __future__ import annotations

from flask import abort, g, request


def check_auth() -> None:
    """Validate the bearer token provided in the request headers."""

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(403, description="Forbidden: Missing or invalid Authorization header")

    token = auth_header.split("Bearer ")[-1].strip()
    if token != g.config["gpt_shared_secret"]:
        abort(403, description="Forbidden: Invalid bearer token")

