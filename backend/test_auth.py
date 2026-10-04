"""Authentication tests. Needs MySQL running with init.sql loaded.

    export DB_PASSWORD="your-mysql-password"
    python test_auth.py

JWT_SECRET is set to a test-only value if you have not set one. The tests use
Flask's test client, so the server does not need to be running and Angular is
not needed. Test users (email starts with 'authtest-') are deleted afterwards.
"""
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")

import jwt
from flask import Flask, g, jsonify
from werkzeug.security import check_password_hash

import auth
import config
import db
from app import app

EMAIL_PREFIX = "authtest-"
PASSWORD = "secret123"


def new_email():
    return f"{EMAIL_PREFIX}{uuid.uuid4().hex[:10]}@example.com"


def db_query(sql, args=()):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def delete_test_users():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email LIKE %s", (EMAIL_PREFIX + "%",))
        conn.commit()
    finally:
        conn.close()


def make_protected_app():
    """A tiny separate app with one route guarded by the real token_required decorator."""
    test_app = Flask("auth_helper_test")
    test_app.register_error_handler(auth.AuthError, auth.handle_auth_error)

    @test_app.get("/protected")
    @auth.token_required
    def protected():
        return jsonify(user=g.current_user)

    return test_app


def make_token(secret=None, algorithm="HS256", **overrides):
    now = datetime.now(timezone.utc)
    payload = {"sub": "1", "role": "student", "iat": now, "exp": now + timedelta(hours=1)}
    payload.update(overrides)
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, secret if secret is not None else config.JWT_SECRET, algorithm=algorithm)


class RegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        delete_test_users()

    @classmethod
    def tearDownClass(cls):
        delete_test_users()

    def register(self, email=None, **fields):
        body = {"name": "Test Student", "email": email or new_email(), "password": PASSWORD}
        body.update(fields)
        return self.client.post("/register", json=body)

    def test_01_registration_works(self):
        resp = self.register()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json(), {"message": "Registration successful"})

    def test_02_password_is_stored_hashed_and_role_is_student(self):
        email = new_email()
        self.assertEqual(self.register(email).status_code, 201)
        (row,) = db_query("SELECT password_hash, role FROM users WHERE email = %s", (email,))
        self.assertNotEqual(row["password_hash"], PASSWORD)
        self.assertNotIn(PASSWORD, row["password_hash"])
        self.assertTrue(check_password_hash(row["password_hash"], PASSWORD))
        self.assertEqual(row["role"], "student")

    def test_03_duplicate_email_is_rejected(self):
        email = new_email()
        self.assertEqual(self.register(email).status_code, 201)
        # Same email with different case and spaces is still a duplicate.
        resp = self.register("  " + email.upper() + "  ")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(len(db_query("SELECT id FROM users WHERE email = %s", (email,))), 1)

    def test_04_name_and_email_are_trimmed_and_email_lowercased(self):
        email = new_email()
        resp = self.register("  " + email.upper() + " ", name="  Padded Name  ")
        self.assertEqual(resp.status_code, 201)
        (row,) = db_query("SELECT name, email FROM users WHERE email = %s", (email,))
        self.assertEqual(row["name"], "Padded Name")
        self.assertEqual(row["email"], email)

    def test_05_client_cannot_choose_admin_role(self):
        email = new_email()
        self.assertEqual(self.register(email, role="admin").status_code, 201)
        (row,) = db_query("SELECT role FROM users WHERE email = %s", (email,))
        self.assertEqual(row["role"], "student")

    def test_06_validation_errors(self):
        cases = {
            "missing name": {"email": new_email(), "password": PASSWORD},
            "missing email": {"name": "A", "password": PASSWORD},
            "missing password": {"name": "A", "email": new_email()},
            "blank name": {"name": "   ", "email": new_email(), "password": PASSWORD},
            "non-string password": {"name": "A", "email": new_email(), "password": 123456},
            "invalid email": {"name": "A", "email": "not-an-email", "password": PASSWORD},
            "short password": {"name": "A", "email": new_email(), "password": "123"},
        }
        for label, body in cases.items():
            with self.subTest(label):
                resp = self.client.post("/register", json=body)
                self.assertEqual(resp.status_code, 400)
                self.assertIn("error", resp.get_json())

    def test_07_missing_or_bad_body_is_rejected(self):
        self.assertEqual(self.client.post("/register").status_code, 400)
        self.assertEqual(
            self.client.post("/register", data="not json", content_type="application/json").status_code, 400
        )
        self.assertEqual(self.client.post("/register", json=["a", "list"]).status_code, 400)


class LoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        delete_test_users()
        cls.email = new_email()
        resp = cls.client.post(
            "/register", json={"name": "Login User", "email": cls.email, "password": PASSWORD}
        )
        assert resp.status_code == 201, resp.get_json()

    @classmethod
    def tearDownClass(cls):
        delete_test_users()

    def login(self, email=None, password=PASSWORD):
        return self.client.post("/login", json={"email": email or self.email, "password": password})

    def test_01_correct_password_logs_in(self):
        resp = self.login()
        self.assertEqual(resp.status_code, 200)

    def test_02_login_returns_token_and_role(self):
        body = self.login().get_json()
        self.assertEqual(set(body), {"token", "role"})
        self.assertEqual(body["role"], "student")
        self.assertTrue(body["token"])

    def test_03_email_is_normalized_on_login(self):
        self.assertEqual(self.login("  " + self.email.upper() + " ").status_code, 200)

    def test_04_wrong_password_is_rejected(self):
        resp = self.login(password="wrong-password")
        self.assertEqual(resp.status_code, 401)
        self.assertNotIn("token", resp.get_json())

    def test_05_unknown_email_is_rejected(self):
        resp = self.login(email=new_email())
        self.assertEqual(resp.status_code, 401)
        # Same message as wrong password, so emails cannot be probed.
        self.assertEqual(resp.get_json(), self.login(password="wrong-password").get_json())

    def test_06_jwt_contains_user_id_and_role(self):
        token = self.login().get_json()["token"]
        claims = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        (row,) = db_query("SELECT id, role FROM users WHERE email = %s", (self.email,))
        self.assertEqual(claims["sub"], str(row["id"]))
        self.assertEqual(claims["role"], row["role"])
        self.assertIn("exp", claims)

    def test_07_responses_never_contain_password_or_hash(self):
        for resp in (self.login(), self.login(password="wrong-password")):
            text = resp.get_data(as_text=True)
            self.assertNotIn(PASSWORD, text)
            self.assertNotIn("scrypt", text)
            self.assertNotIn("password_hash", text)

    def test_08_missing_fields_and_body(self):
        self.assertEqual(self.client.post("/login", json={"email": self.email}).status_code, 400)
        self.assertEqual(self.client.post("/login", json={"password": PASSWORD}).status_code, 400)
        self.assertEqual(self.client.post("/login").status_code, 400)

    def test_09_demo_admin_can_log_in(self):
        resp = self.client.post(
            "/login", json={"email": "admin@campusnotes.demo", "password": "Admin@123"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["role"], "admin")

    def test_10_missing_jwt_secret_gives_server_error_not_a_token(self):
        with patch.object(config, "JWT_SECRET", None):
            resp = self.login()
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("token", resp.get_json())


class AuthHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = make_protected_app().test_client()

    def get(self, header=None):
        headers = {"Authorization": header} if header is not None else {}
        return self.client.get("/protected", headers=headers)

    def test_01_missing_token_is_rejected(self):
        resp = self.get()
        self.assertEqual(resp.status_code, 401)
        self.assertIn("missing", resp.get_json()["error"].lower())

    def test_02_invalid_tokens_are_rejected(self):
        bad = {
            "garbage": "Bearer not.a.token",
            "wrong signature": "Bearer " + make_token(secret="some-other-secret-0123456789abcdef"),
            "unsigned (alg none)": "Bearer " + make_token(secret="", algorithm="none"),
            "no role claim": "Bearer " + make_token(role=None),
            "non-numeric id": "Bearer " + make_token(sub="abc"),
            "wrong scheme": "Token " + make_token(),
            "no token after Bearer": "Bearer",
        }
        for label, header in bad.items():
            with self.subTest(label):
                resp = self.get(header)
                self.assertEqual(resp.status_code, 401)
                self.assertIn("error", resp.get_json())

    def test_03_expired_token_is_rejected(self):
        expired = make_token(exp=datetime.now(timezone.utc) - timedelta(hours=1))
        resp = self.get("Bearer " + expired)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("expired", resp.get_json()["error"].lower())

    def test_04_valid_token_gives_user_to_the_route(self):
        token = auth.create_token(42, "admin")
        resp = self.get("Bearer " + token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"], {"id": 42, "role": "admin"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
