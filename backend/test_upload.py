"""Student note upload tests (POST /notes). Needs MySQL with init.sql loaded.

    export DB_PASSWORD="your-mysql-password"
    python test_upload.py

Uses Flask's test client, so the server does not need to be running. The tests
register their own temporary students (email starts with 'uploadtest-'), log in
through the real /login route, and upload temporary PDFs (title starts with
'uploadtest-'). Every temporary user, note and uploaded file is removed
afterwards. Permanent seed data is only read, never changed.

The last test class re-runs the Stage 3 (auth), Stage 4 (browse) and Stage 5
(notes) test suites.
"""
import hashlib
import io
import os
import re
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")

import pymysql

import auth
import config
import db
from app import app

PREFIX = "uploadtest-"
PASSWORD = "secret123"
UPLOADS = config.UPLOADS_DIR
SEED_FILES = config.SEED_FILES_DIR
STORED_PATH_RE = re.compile(r"uploads/[0-9a-f]{32}\.pdf")
SUCCESS_BODY = {"message": "Note uploaded for approval", "status": "pending"}

DEFAULT = object()  # "use the normal valid value" (None means "leave the field out")


def run_sql(sql, args=(), commit=False):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
            last_id = cur.lastrowid
        if commit:
            conn.commit()
        return rows, last_id
    finally:
        conn.close()


def pdf_bytes(tag):
    return b"%PDF-1.4\n% " + tag.encode() + b"\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def names_in(folder):
    """File names in a folder (ignoring the .gitkeep placeholder)."""
    return {p.name for p in folder.iterdir() if p.name != ".gitkeep"}


def tree_snapshot(root):
    """Every file under the project root as {relative path: size}, ignoring uploads/ and caches."""
    skip_dirs = {"node_modules", "__pycache__", ".angular", ".git", ".venv", "venv"}
    snapshot = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        if os.path.abspath(folder) == str(UPLOADS):
            dirs[:] = []
            continue
        for name in files:
            full = os.path.join(folder, name)
            snapshot[os.path.relpath(full, root)] = os.path.getsize(full)
    return snapshot


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_notes_count(title):
    rows, _ = run_sql("SELECT COUNT(*) AS c FROM notes WHERE title = %s", (title,))
    return rows[0]["c"]


class FailOnInsertCursor:
    """Wraps a real cursor but fails when a note INSERT is attempted."""

    def __init__(self, real):
        self._real = real

    def __enter__(self):
        self._real.__enter__()
        return self

    def __exit__(self, *exc):
        return self._real.__exit__(*exc)

    def execute(self, sql, args=None):
        if sql.lstrip().upper().startswith("INSERT"):
            raise pymysql.err.OperationalError(2013, "Lost connection to MySQL server")
        return self._real.execute(sql, args)

    def __getattr__(self, name):
        return getattr(self._real, name)


class BrokenConnection:
    """Wraps a real connection so the INSERT (or the commit) fails."""

    def __init__(self, fail="insert"):
        self._real = db.get_connection()
        self._fail = fail
        self.closed = False

    def cursor(self):
        real = self._real.cursor()
        return FailOnInsertCursor(real) if self._fail == "insert" else real

    def commit(self):
        if self._fail == "commit":
            raise pymysql.err.OperationalError(2013, "Lost connection during commit")
        self._real.commit()

    def close(self):
        self.closed = True
        self._real.close()


class UploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.tok = uuid.uuid4().hex[:8]
        cls.cleanup_database()

        # Two temporary students, created through the real register + login routes.
        cls.alice = cls.make_student("alice")
        cls.bob = cls.make_student("bob")
        cls.admin_token = auth.create_token(1, "admin")  # a signed admin token (id 1 = demo admin)

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_database()

    @classmethod
    def cleanup_database(cls):
        run_sql("DELETE FROM notes WHERE title LIKE %s", (PREFIX + "%",), commit=True)
        run_sql(
            "DELETE FROM notes WHERE uploader_id IN (SELECT id FROM users WHERE email LIKE %s)",
            (PREFIX + "%",),
            commit=True,
        )
        run_sql("DELETE FROM users WHERE email LIKE %s", (PREFIX + "%",), commit=True)

    @classmethod
    def make_student(cls, label):
        email = f"{PREFIX}{label}-{cls.tok}@example.com"
        resp = cls.client.post("/register", json={"name": f"Upload {label}", "email": email, "password": PASSWORD})
        assert resp.status_code == 201, resp.get_data(as_text=True)
        resp = cls.client.post("/login", json={"email": email, "password": PASSWORD})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        token = resp.get_json()["token"]
        return {"token": token, "id": auth.decode_token(token)["id"], "email": email}

    def setUp(self):
        self.files_before = names_in(UPLOADS)

    def tearDown(self):
        # Remove every note and file created by this test.
        for name in names_in(UPLOADS) - self.files_before:
            try:
                (UPLOADS / name).unlink()
            except FileNotFoundError:
                pass
        run_sql("DELETE FROM notes WHERE title LIKE %s", (PREFIX + "%",), commit=True)

    # ---- helpers -------------------------------------------------------

    def title(self, label="Operating Systems Unit 1"):
        return f"{PREFIX}{self.tok} {label}"

    def upload(self, token=DEFAULT, title=DEFAULT, description=DEFAULT, unit_id=DEFAULT,
               content=DEFAULT, filename="notes.pdf", content_type="application/pdf",
               include_file=True, extra=None):
        """POST /notes as a multipart form. Pass None to leave a field out."""
        data = {}
        if title is DEFAULT:
            title = self.title()
        if description is DEFAULT:
            description = "Process management notes"
        if unit_id is DEFAULT:
            unit_id = 5
        if token is DEFAULT:
            token = self.alice["token"]
        if content is DEFAULT:
            content = pdf_bytes(uuid.uuid4().hex)

        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if unit_id is not None:
            data["unit_id"] = str(unit_id)
        if include_file:
            data["file"] = (io.BytesIO(content), filename, content_type)
        if extra:
            data.update(extra)

        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post("/notes", data=data, headers=headers, content_type="multipart/form-data")

    def rows_for(self, title):
        rows, _ = run_sql("SELECT * FROM notes WHERE title = %s ORDER BY id", (title,))
        return list(rows)

    def assert_rejected(self, resp, status, title=None):
        """The request failed cleanly: JSON error, no database row, no file left on disk."""
        self.assertEqual(resp.status_code, status, resp.get_data(as_text=True)[:300])
        body = resp.get_json()
        self.assertEqual(set(body), {"error"})
        self.assertTrue(body["error"])
        self.assertEqual(self.rows_for(title or self.title()), [])
        self.assertEqual(names_in(UPLOADS), self.files_before)

    # ---- 1-5: the happy path ----------------------------------------------

    def test_01_student_can_upload_valid_pdf(self):
        resp = self.upload()
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json(), SUCCESS_BODY)

    def test_02_upload_creates_database_record(self):
        content = pdf_bytes("record")
        self.assertEqual(self.upload(content=content, unit_id=6).status_code, 201)

        rows = self.rows_for(self.title())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["description"], "Process management notes")
        self.assertEqual(row["unit_id"], 6)
        self.assertEqual(row["file_type"], "pdf")
        self.assertEqual(row["download_count"], 0)
        self.assertIsNotNone(row["created_at"])
        self.assertRegex(row["file_path"], STORED_PATH_RE)

    def test_03_new_note_is_pending(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.rows_for(self.title())[0]["status"], "pending")

    def test_04_uploader_id_comes_from_the_jwt(self):
        self.assertNotEqual(self.alice["id"], self.bob["id"])
        # A client-supplied uploader_id (here: the admin's id, and Bob's) is ignored.
        resp = self.upload(title=self.title("alice"), extra={"uploader_id": "1", "user_id": str(self.bob["id"])})
        self.assertEqual(resp.status_code, 201)
        resp = self.upload(title=self.title("bob"), token=self.bob["token"], extra={"uploader_id": str(self.alice["id"])})
        self.assertEqual(resp.status_code, 201)

        self.assertEqual(self.rows_for(self.title("alice"))[0]["uploader_id"], self.alice["id"])
        self.assertEqual(self.rows_for(self.title("bob"))[0]["uploader_id"], self.bob["id"])

    def test_05_uploaded_file_exists_in_uploads_folder(self):
        content = pdf_bytes("on-disk")
        seed_before = names_in(SEED_FILES)
        self.assertEqual(self.upload(content=content).status_code, 201)

        stored = self.rows_for(self.title())[0]["file_path"]
        full = config.BASE_DIR / stored
        self.assertTrue(full.is_file())
        self.assertEqual(full.resolve().parent, UPLOADS.resolve())
        self.assertEqual(full.read_bytes(), content)
        self.assertEqual(names_in(UPLOADS) - self.files_before, {full.name})
        self.assertEqual(names_in(SEED_FILES), seed_before)  # nothing written to seed_files/

    # ---- 6-7: who may upload --------------------------------------------

    def test_06_admin_cannot_use_student_upload_endpoint(self):
        resp = self.upload(token=self.admin_token)
        self.assert_rejected(resp, 403)
        self.assertIn("student", resp.get_json()["error"].lower())

    def test_07_unauthenticated_upload_is_rejected(self):
        cases = {
            "no header": None,
            "garbage token": "not-a-real-token",
            "wrong signature": auth.create_token(self.alice["id"], "student")[:-4] + "AAAA",
        }
        for label, token in cases.items():
            with self.subTest(label):
                resp = self.upload(token=token)
                self.assert_rejected(resp, 401)
                self.assertEqual(resp.headers.get("WWW-Authenticate"), "Bearer")

    # ---- 8-14: validation ---------------------------------------------------

    def test_08_missing_title_is_rejected(self):
        self.assert_rejected(self.upload(title=None), 400)

    def test_09_blank_title_is_rejected(self):
        for blank in ("", "   ", "\t\n "):
            with self.subTest(blank=repr(blank)):
                resp = self.upload(title=blank)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(names_in(UPLOADS), self.files_before)
        rows, _ = run_sql(
            "SELECT COUNT(*) AS c FROM notes WHERE uploader_id = %s", (self.alice["id"],)
        )
        self.assertEqual(rows[0]["c"], 0)

    def test_09b_overlong_title_is_rejected(self):
        long_title = PREFIX + "x" * 200
        self.assert_rejected(self.upload(title=long_title), 400, title=long_title)

    def test_10_missing_unit_id_is_rejected(self):
        self.assert_rejected(self.upload(unit_id=None), 400)

    def test_11_invalid_unit_id_is_rejected(self):
        for bad in ("abc", "0", "-1", "1.5", "5; DROP TABLE notes", "", " 5", "99999999999"):
            with self.subTest(unit_id=bad):
                resp = self.upload(unit_id=bad)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(set(resp.get_json()), {"error"})
                self.assertEqual(names_in(UPLOADS), self.files_before)
        self.assertEqual(self.rows_for(self.title()), [])

    def test_11b_unit_that_does_not_exist_returns_404(self):
        resp = self.upload(unit_id=999999)
        self.assert_rejected(resp, 404)
        self.assertEqual(resp.get_json(), {"error": "Unit not found"})

    def test_12_missing_file_is_rejected(self):
        self.assert_rejected(self.upload(include_file=False), 400)
        # A browser sends an empty file part when no file was chosen.
        self.assert_rejected(self.upload(filename=""), 400)

    def test_13_non_pdf_file_is_rejected(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        cases = {
            "text file": dict(content=b"just some text", filename="notes.txt", content_type="text/plain"),
            "text pretending to be .pdf": dict(content=b"just some text", filename="notes.pdf"),
            "png renamed to .pdf": dict(content=png, filename="notes.pdf"),
            "png with png name": dict(content=png, filename="picture.png", content_type="image/png"),
            "script": dict(content=b"<?php echo 1;", filename="shell.php", content_type="application/x-php"),
            "pdf bytes, .exe name": dict(content=pdf_bytes("x"), filename="notes.exe"),
            "double extension": dict(content=pdf_bytes("x"), filename="notes.pdf.exe"),
            "no extension": dict(content=pdf_bytes("x"), filename="notes"),
            "pdf bytes, image content type": dict(content=pdf_bytes("x"), filename="notes.pdf", content_type="image/png"),
            "truncated header": dict(content=b"%PD", filename="notes.pdf"),
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                self.assert_rejected(self.upload(**kwargs), 400)

    def test_14_empty_file_is_rejected(self):
        resp = self.upload(content=b"")
        self.assert_rejected(resp, 400)
        self.assertIn("empty", resp.get_json()["error"].lower())

    def test_14b_request_that_is_not_multipart_is_rejected(self):
        resp = self.client.post(
            "/notes",
            json={"title": self.title(), "unit_id": 5},
            headers={"Authorization": f"Bearer {self.alice['token']}"},
        )
        self.assert_rejected(resp, 400)

    def test_14c_file_over_the_size_limit_is_rejected(self):
        header = b"%PDF-1.4\n"
        # One byte over the limit is rejected by the route itself...
        resp = self.upload(content=header + b"0" * (config.MAX_UPLOAD_BYTES + 1 - len(header)))
        self.assert_rejected(resp, 413)
        self.assertIn("too large", resp.get_json()["error"].lower())
        # ...a request far over the limit is stopped before the form is even parsed...
        resp = self.upload(content=header + b"0" * (config.MAX_UPLOAD_BYTES + 200 * 1024))
        self.assert_rejected(resp, 413)
        # ...and a file exactly at the limit is still accepted.
        resp = self.upload(content=header + b"0" * (config.MAX_UPLOAD_BYTES - len(header)))
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True)[:200])

    # ---- 15-16: file storage safety -------------------------------------------

    def test_15_two_uploads_do_not_overwrite_each_other(self):
        first, second, third = pdf_bytes("first"), pdf_bytes("second"), pdf_bytes("third")
        # Same title, same file name, by two different students.
        self.assertEqual(self.upload(content=first, filename="same.pdf").status_code, 201)
        self.assertEqual(self.upload(content=second, filename="same.pdf").status_code, 201)
        self.assertEqual(self.upload(content=third, filename="same.pdf", token=self.bob["token"]).status_code, 201)

        rows = self.rows_for(self.title())
        self.assertEqual(len(rows), 3)
        paths = [r["file_path"] for r in rows]
        self.assertEqual(len(set(paths)), 3)
        self.assertEqual([(config.BASE_DIR / p).read_bytes() for p in paths], [first, second, third])
        self.assertEqual(len(names_in(UPLOADS) - self.files_before), 3)

    def test_15b_server_never_overwrites_an_existing_file(self):
        """Even if a generated name collided with an existing file, that file must survive."""
        fixed = uuid.UUID("12345678123456781234567812345678")
        victim = UPLOADS / (fixed.hex + ".pdf")
        victim.write_bytes(b"%PDF-1.4 precious")
        try:
            with patch("routes.notes_routes.uuid.uuid4", return_value=fixed):
                resp = self.upload()
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(set(resp.get_json()), {"error"})
            self.assertEqual(self.rows_for(self.title()), [])
            self.assertEqual(names_in(UPLOADS), self.files_before | {victim.name})
            self.assertEqual(victim.read_bytes(), b"%PDF-1.4 precious")
        finally:
            victim.unlink()

    def test_16_dangerous_filename_cannot_escape_uploads_folder(self):
        project_root = config.BASE_DIR.parent
        config_hash = sha256(config.BASE_DIR / "config.py")
        app_hash = sha256(config.BASE_DIR / "app.py")
        tree_before = tree_snapshot(project_root)

        evil_names = [
            "../../evil.pdf",
            "../evil.pdf",
            "..\\..\\evil.pdf",
            "/etc/passwd.pdf",
            "C:\\Windows\\System32\\evil.pdf",
            "../config.py.pdf",
            "uploads/../app.py.pdf",
            "....//....//evil.pdf",
            "%2e%2e%2fevil.pdf",
            "evil\x00.pdf",
            "..",
            "",
            ".pdf",
            "   .pdf",
            "NOTES.PDF",
        ]
        for i, name in enumerate(evil_names):
            with self.subTest(filename=name):
                title = self.title(f"evil {i}")
                resp = self.upload(title=title, filename=name)
                self.assertIn(resp.status_code, (201, 400))

                rows = self.rows_for(title)
                if resp.status_code == 400:
                    self.assertEqual(rows, [])
                    continue
                # If it was accepted, it must be stored under a server-made name inside uploads/.
                self.assertEqual(len(rows), 1)
                stored = rows[0]["file_path"]
                self.assertRegex(stored, STORED_PATH_RE)
                full = (config.BASE_DIR / stored).resolve()
                self.assertTrue(full.is_file())
                self.assertEqual(full.parent, UPLOADS.resolve())
                self.assertNotIn("evil", stored)

        # Nothing was created or changed anywhere else in the project.
        self.assertEqual(config_hash, sha256(config.BASE_DIR / "config.py"))
        self.assertEqual(app_hash, sha256(config.BASE_DIR / "app.py"))
        self.assertEqual(tree_before, tree_snapshot(project_root))
        for new_file in names_in(UPLOADS) - self.files_before:
            self.assertRegex("uploads/" + new_file, STORED_PATH_RE)
        self.assertFalse((project_root / "evil.pdf").exists())
        self.assertFalse((config.BASE_DIR.parent.parent / "evil.pdf").exists())

    def test_16b_uppercase_pdf_extension_is_stored_as_lowercase_pdf(self):
        self.assertEqual(self.upload(filename="NOTES.PDF").status_code, 201)
        self.assertRegex(self.rows_for(self.title())[0]["file_path"], STORED_PATH_RE)

    # ---- 17: failures leave nothing behind ----------------------------------

    def test_17_database_failure_does_not_leave_orphaned_file(self):
        broken = BrokenConnection(fail="insert")
        with patch("db.get_connection", return_value=broken):
            resp = self.upload()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json(), {"error": "Database unavailable"})
        self.assertEqual(names_in(UPLOADS), self.files_before)  # file was removed again
        self.assertEqual(self.rows_for(self.title()), [])
        self.assertTrue(broken.closed)

    def test_17b_commit_failure_does_not_leave_orphaned_file(self):
        broken = BrokenConnection(fail="commit")
        with patch("db.get_connection", return_value=broken):
            resp = self.upload()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(names_in(UPLOADS), self.files_before)
        self.assertEqual(self.rows_for(self.title()), [])
        self.assertTrue(broken.closed)

    def test_17c_database_down_saves_nothing(self):
        error = pymysql.err.OperationalError(2003, "Can't connect to MySQL server")
        with patch("db.get_connection", side_effect=error):
            resp = self.upload()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(names_in(UPLOADS), self.files_before)

    def test_17d_file_save_failure_creates_no_database_record(self):
        with patch("routes.notes_routes.shutil.copyfileobj", side_effect=OSError("disk full")):
            resp = self.upload()
        self.assert_rejected(resp, 500)  # also proves the half-written file was removed
        self.assertNotIn("disk full", resp.get_data(as_text=True))  # no internals leak

    # ---- the pending note stays hidden --------------------------------------

    def test_18_pending_upload_is_not_visible_to_students(self):
        approved_before = self.client.get("/notes").get_json()
        self.assertEqual(self.upload().status_code, 201)
        note_id = self.rows_for(self.title())[0]["id"]

        self.assertEqual(self.client.get("/notes").get_json(), approved_before)
        self.assertEqual(self.client.get("/notes", query_string={"q": PREFIX + self.tok}).get_json(), [])
        self.assertEqual(self.client.get(f"/notes/{note_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/notes/{note_id}/download").status_code, 404)
        self.assertEqual(self.rows_for(self.title())[0]["download_count"], 0)

    def test_19_existing_get_notes_still_works_alongside_post(self):
        self.assertEqual(self.client.get("/notes").status_code, 200)
        self.assertEqual(self.client.put("/notes").status_code, 405)
        self.assertEqual(self.client.delete("/notes").status_code, 405)


class RegressionTests(unittest.TestCase):
    """Re-run the earlier stages' test suites."""

    def run_suite(self, suite):
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        self.assertTrue(result.wasSuccessful(), stream.getvalue())
        return result.testsRun

    def test_20_stage3_auth_tests_still_pass(self):
        import test_auth

        suite = unittest.defaultTestLoader.loadTestsFromModule(test_auth)
        self.assertGreater(self.run_suite(suite), 0)

    def test_21_stage4_browse_tests_still_pass(self):
        import test_browse

        suite = unittest.defaultTestLoader.loadTestsFromModule(test_browse)
        self.assertGreater(self.run_suite(suite), 0)

    def test_22_stage5_notes_tests_still_pass(self):
        import test_notes

        # Only the notes tests: test_notes' own regression class re-runs auth and browse again.
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_notes.NotesTests)
        self.assertGreater(self.run_suite(suite), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
