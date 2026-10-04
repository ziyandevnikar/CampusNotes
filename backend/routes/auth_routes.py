"""POST /register and POST /login."""
import re

import pymysql
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import auth
import db

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128


def _error(message, status):
    return jsonify({"error": message}), status


def _read_fields(*names):
    """Return (values, error_response). values is a dict of the raw string fields."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, _error("Request body must be a JSON object", 400)

    values = {n: data.get(n) for n in names}
    missing = [n for n, v in values.items() if not isinstance(v, str) or not v.strip()]
    if missing:
        return None, _error("Missing or invalid required field(s): " + ", ".join(missing), 400)
    return values, None


@auth_bp.post("/register")
def register():
    values, err = _read_fields("name", "email", "password")
    if err:
        return err

    name = values["name"].strip()
    email = values["email"].strip().lower()
    password = values["password"]

    if len(name) > 100:
        return _error("Name must be at most 100 characters", 400)
    if len(email) > 255 or not EMAIL_RE.match(email):
        return _error("Invalid email address", 400)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return _error(
            f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters", 400
        )

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return _error("Email is already registered", 409)

            # Role is always 'student'; any role sent by the client is ignored.
            cur.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'student')",
                (name, email, generate_password_hash(password)),
            )
        conn.commit()
    except pymysql.err.IntegrityError:
        # Two requests registered the same email at the same moment.
        conn.rollback()
        return _error("Email is already registered", 409)
    finally:
        conn.close()

    return jsonify({"message": "Registration successful"}), 201


@auth_bp.post("/login")
def login():
    values, err = _read_fields("email", "password")
    if err:
        return err

    email = values["email"].strip().lower()
    password = values["password"]

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash, role FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
    finally:
        conn.close()

    # Same message for unknown email and wrong password, so emails cannot be probed.
    if user is None or not check_password_hash(user["password_hash"], password):
        return _error("Invalid email or password", 401)

    token = auth.create_token(user["id"], user["role"])
    return jsonify({"token": token, "role": user["role"]}), 200
