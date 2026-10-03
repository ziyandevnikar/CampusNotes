"""JWT helpers: create tokens, read the Authorization header, protect routes.

Protecting a route (later stages):

    from auth import token_required
    from flask import g

    @bp.get("/something")
    @token_required
    def something():
        user = g.current_user      # {"id": 2, "role": "student"}
"""
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, jsonify, request

import config

log = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when a request is not authenticated. Returned to the client as JSON."""

    def __init__(self, message, status=401):
        super().__init__(message)
        self.message = message
        self.status = status


class ConfigError(Exception):
    """Raised when the server is misconfigured (for example JWT_SECRET is not set)."""


def _secret():
    if not config.JWT_SECRET:
        raise ConfigError("JWT_SECRET environment variable is not set")
    return config.JWT_SECRET


def create_token(user_id, role):
    """Return a signed JWT. The user id goes in the standard 'sub' claim (as a string)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _secret(), algorithm=config.JWT_ALGORITHM)


def decode_token(token):
    """Validate a JWT and return {"id": int, "role": str}. Raises AuthError if it is bad."""
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[config.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise AuthError("Invalid token")
    return {"id": user_id, "role": payload["role"]}


def get_current_user():
    """Read 'Authorization: Bearer <token>' from the request and return the user dict."""
    header = request.headers.get("Authorization")
    if not header:
        raise AuthError("Authorization header is missing")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Authorization header must be in the format: Bearer <token>")
    return decode_token(parts[1])


def token_required(view):
    """Decorator: reject the request unless it carries a valid token.

    On success the user is available as flask.g.current_user.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        g.current_user = get_current_user()
        return view(*args, **kwargs)

    return wrapper


def handle_auth_error(err):
    return jsonify({"error": err.message}), err.status, {"WWW-Authenticate": "Bearer"}


def handle_config_error(err):
    log.error("Server configuration error: %s", err)
    return jsonify({"error": "Server configuration error"}), 500
