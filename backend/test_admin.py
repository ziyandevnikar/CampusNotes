"""Admin moderation tests. Needs MySQL with init.sql loaded.

    export DB_PASSWORD="your-mysql-password"
    python test_admin.py

Uses Flask's test client. The tests register temporary students (email starts
with 'admintest-'), create temporary notes (title starts with 'admintest-') and
temporary PDFs in uploads/, and remove all of them afterwards. Permanent seed
data is only read, never changed. The last test class re-runs the Stage 3-6
test suites.
"""
import io
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")

import auth
import config
from app import app
from test_upload import BrokenConnection, names_in, pdf_bytes, run_sql

PREFIX = "admintest-"
PASSWORD = "secret123"
UPLOADS = config.UPLOADS_DIR
SECRET_MARKER = b"TOP-SECRET-OUTSIDE-FILE"
PUBLIC_KEYS = {
    "id", "title", "description", "unit_id", "uploader_id", "file_type", "status",
    "created_at", "download_count", "subject", "unit", "file_url",
}


class EmptyConnection:
    """Stands in for the database when there is nothing pending: an admin user, no notes."""

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        pass

    def fetchone(self):
        return {"role": "admin"}

    def fetchall(self):
        return []

    def close(self):
        pass


class TrackingBrokenConnection(BrokenConnection):
    """A connection whose commit fails; remembers whether rollback was called."""

    rolled_back = False

    def rollback(self):
        self.rolled_back = True
        self._real.rollback()


class AdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.tok = uuid.uuid4().hex[:8]
        cls.cleanup_database()
        cls.alice = cls.make_student("alice")
        cls.bob = cls.make_student("bob")
        cls.admin_token = auth.create_token(1, "admin")  # id 1 is the demo admin
        cls.admin = {"Authorization": f"Bearer {cls.admin_token}"}
        cls.student = {"Authorization": f"Bearer {cls.alice['token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_database()

    @classmethod
    def cleanup_database(cls):
        run_sql("DELETE FROM notes WHERE title LIKE %s", (PREFIX + "%",), commit=True)
        run_sql(
            "DELETE FROM notes WHERE uploader_id IN (SELECT id FROM users WHERE email LIKE %s)",
            (PREFIX + "%",), commit=True,
        )
        run_sql("DELETE FROM users WHERE email LIKE %s", (PREFIX + "%",), commit=True)

    @classmethod
    def make_student(cls, label):
        email = f"{PREFIX}{label}-{cls.tok}@example.com"
        resp = cls.client.post("/register", json={"name": f"Admin test {label}", "email": email, "password": PASSWORD})
        assert resp.status_code == 201, resp.get_data(as_text=True)
        token = cls.client.post("/login", json={"email": email, "password": PASSWORD}).get_json()["token"]
        return {"token": token, "id": auth.decode_token(token)["id"], "email": email}

    def setUp(self):
        self.files_before = names_in(UPLOADS)
        self.extra_files = []
        self.counter = 0

    def tearDown(self):
        run_sql("DELETE FROM notes WHERE title LIKE %s", (PREFIX + "%",), commit=True)
        for name in names_in(UPLOADS) - self.files_before:
            try:
                (UPLOADS / name).unlink()
            except FileNotFoundError:
                pass
        for f in self.extra_files:
            try:
                f.unlink()
            except (FileNotFoundError, OSError):
                pass

    # ---- helpers ---------------------------------------------------------

    def add_note(self, status="pending", content=None, file_path=None, label="note"):
        """Insert a temporary note (and a real PDF in uploads/ unless file_path is given)."""
        self.counter += 1
        title = f"{PREFIX}{self.tok} {label} {self.counter} {status}"
        if file_path is None:
            name = f"{PREFIX}{self.tok}-{uuid.uuid4().hex[:6]}.pdf"
            content = content or pdf_bytes(title)
            (UPLOADS / name).write_bytes(content)
            file_path = f"uploads/{name}"
        _, note_id = run_sql(
            "INSERT INTO notes (title, description, unit_id, uploader_id, file_path, status) "
            "VALUES (%s, %s, 5, %s, %s, %s)",
            (title, "temporary test note", self.alice["id"], file_path, status), commit=True,
        )
        return note_id

    def status_of(self, note_id):
        rows, _ = run_sql("SELECT status FROM notes WHERE id = %s", (note_id,))
        return rows[0]["status"]

    def count_of(self, note_id):
        rows, _ = run_sql("SELECT download_count FROM notes WHERE id = %s", (note_id,))
        return rows[0]["download_count"]

    def admin_get(self, url, status=200):
        resp = self.client.get(url, headers=self.admin)
        self.assertEqual(resp.status_code, status, resp.get_data(as_text=True)[:300])
        resp.close()
        return resp

    def patch(self, note_id, action, headers=None):
        return self.client.patch(f"/admin/notes/{note_id}/{action}", headers=headers or self.admin)

    def student_ids(self, url="/notes"):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return [n["id"] for n in resp.get_json()]

    def assert_hidden_from_students(self, note_id, title):
        self.assertNotIn(note_id, self.student_ids())
        self.assertNotIn(note_id, self.student_ids("/notes?q=" + PREFIX + self.tok))
        self.assertEqual(self.client.get(f"/notes/{note_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/notes/{note_id}/download").status_code, 404)

    # ---- 1-5: pending list --------------------------------------------------

    def test_01_admin_can_access_pending_notes(self):
        resp = self.client.get("/admin/notes/pending", headers=self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.get_json()), ["notes"])
        self.assertIsInstance(resp.get_json()["notes"], list)

    def test_02_student_cannot_access_pending_notes(self):
        resp = self.client.get("/admin/notes/pending", headers=self.student)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(set(resp.get_json()), {"error"})

    def test_03_unauthenticated_user_cannot_access_admin_endpoints(self):
        note_id = self.add_note()
        calls = [
            ("get", "/admin/notes/pending"), ("get", f"/admin/notes/{note_id}"),
            ("get", f"/admin/notes/{note_id}/download"),
            ("patch", f"/admin/notes/{note_id}/approve"), ("patch", f"/admin/notes/{note_id}/reject"),
        ]
        for token in (None, "garbage", self.admin_token[:-4] + "AAAA"):
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            for method, url in calls:
                with self.subTest(method=method, url=url, token=bool(token)):
                    resp = getattr(self.client, method)(url, headers=headers)
                    self.assertEqual(resp.status_code, 401)
        self.assertEqual(self.status_of(note_id), "pending")

    def test_04_pending_notes_are_returned(self):
        pending = self.add_note("pending")
        approved = self.add_note("approved")
        rejected = self.add_note("rejected")
        notes = self.admin_get("/admin/notes/pending").get_json()["notes"]
        ids = [n["id"] for n in notes]
        self.assertIn(pending, ids)
        self.assertNotIn(approved, ids)
        self.assertNotIn(rejected, ids)
        self.assertTrue(all(n["status"] == "pending" for n in notes))

        mine = next(n for n in notes if n["id"] == pending)
        self.assertEqual(set(mine), PUBLIC_KEYS)  # nothing else (no emails, hashes, paths) leaks
        self.assertEqual(mine["uploader_id"], self.alice["id"])
        self.assertEqual(mine["unit_id"], 5)
        self.assertEqual(mine["file_type"], "pdf")
        self.assertEqual(mine["subject"], "Data Structures")
        self.assertEqual(mine["unit"], "Unit 2: Stacks and Queues")
        self.assertRegex(mine["created_at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_05_empty_pending_list_returns_200_and_empty_list(self):
        # The seed data already contains a pending note and must not be changed,
        # so the empty case is checked against a stand-in database.
        with patch("db.get_connection", return_value=EmptyConnection()):
            resp = self.client.get("/admin/notes/pending", headers=self.admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"notes": []})

    # ---- 6-7: detail and review download --------------------------------------

    def test_06_admin_can_retrieve_note_detail(self):
        note_id = self.add_note("pending")
        data = self.admin_get(f"/admin/notes/{note_id}").get_json()
        self.assertEqual(set(data), PUBLIC_KEYS)
        self.assertEqual(data["id"], note_id)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["file_url"], f"/admin/notes/{note_id}/download")
        for status in ("approved", "rejected"):  # detail works for every status
            other = self.add_note(status)
            self.assertEqual(self.admin_get(f"/admin/notes/{other}").get_json()["status"], status)

    def test_07_admin_can_review_download_pending_pdf(self):
        content = pdf_bytes("review-me")
        for status in ("pending", "rejected", "approved"):
            with self.subTest(status=status):
                note_id = self.add_note(status, content=content)
                resp = self.client.get(f"/admin/notes/{note_id}/download", headers=self.admin)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.get_data(), content)
                self.assertIn("attachment", resp.headers["Content-Disposition"])
                resp.close()
                self.assertEqual(self.count_of(note_id), 0)  # reviewing is not a student download
        # the student-facing rule is not weakened
        pending = self.add_note("pending")
        self.assertEqual(self.client.get(f"/notes/{pending}/download").status_code, 404)

    # ---- 8-10: approve ----------------------------------------------------------

    def test_08_admin_can_approve_pending_note(self):
        note_id = self.add_note("pending")
        other = self.add_note("pending")
        resp = self.patch(note_id, "approve")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"message": "Note approved", "status": "approved"})
        self.assertEqual(self.status_of(other), "pending")  # only the chosen note changed

    def test_09_approval_changes_status_to_approved(self):
        note_id = self.add_note("pending")
        self.assertEqual(self.status_of(note_id), "pending")
        self.patch(note_id, "approve")
        self.assertEqual(self.status_of(note_id), "approved")
        self.assertNotIn(note_id, [n["id"] for n in self.admin_get("/admin/notes/pending").get_json()["notes"]])

    def test_10_approved_note_becomes_visible_to_students(self):
        content = pdf_bytes("visible")
        note_id = self.add_note("pending", content=content)
        self.assert_hidden_from_students(note_id, "")
        self.patch(note_id, "approve")

        self.assertIn(note_id, self.student_ids())
        self.assertIn(note_id, self.student_ids("/notes?q=" + PREFIX + self.tok))
        self.assertIn(note_id, self.student_ids("/notes?unit_id=5"))
        self.assertEqual(self.client.get(f"/notes/{note_id}").status_code, 200)
        resp = self.client.get(f"/notes/{note_id}/download")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(), content)
        resp.close()
        self.assertEqual(self.count_of(note_id), 1)

    # ---- 11-13: reject ----------------------------------------------------------

    def test_11_admin_can_reject_pending_note(self):
        note_id = self.add_note("pending")
        resp = self.patch(note_id, "reject")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"message": "Note rejected", "status": "rejected"})

    def test_12_rejection_changes_status_to_rejected(self):
        note_id = self.add_note("pending")
        self.patch(note_id, "reject")
        self.assertEqual(self.status_of(note_id), "rejected")
        self.assertNotIn(note_id, [n["id"] for n in self.admin_get("/admin/notes/pending").get_json()["notes"]])

    def test_13_rejected_note_does_not_appear_for_students(self):
        note_id = self.add_note("pending")
        self.patch(note_id, "reject")
        self.assert_hidden_from_students(note_id, "")
        # the admin can still look at it
        self.assertEqual(self.admin_get(f"/admin/notes/{note_id}").get_json()["status"], "rejected")
        self.assertEqual(self.client.get(f"/admin/notes/{note_id}/download", headers=self.admin).status_code, 200)

    # ---- 14-16: bad ids and repeated moderation -------------------------------------

    def test_14_nonexistent_note_returns_404(self):
        for url, method in ((f"/admin/notes/{n}", "get") for n in (99999999,)):
            self.assertEqual(self.client.get(url, headers=self.admin).status_code, 404)
        self.assertEqual(self.client.get("/admin/notes/99999999/download", headers=self.admin).status_code, 404)
        for action in ("approve", "reject"):
            resp = self.patch(99999999, action)
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.get_json(), {"error": "Note not found"})

    def test_14b_invalid_note_id_returns_400(self):
        for bad in ("abc", "0", "-1", "1.5", "99999999999"):
            with self.subTest(note_id=bad):
                self.assertEqual(self.client.get(f"/admin/notes/{bad}", headers=self.admin).status_code, 400)
                self.assertEqual(self.client.get(f"/admin/notes/{bad}/download", headers=self.admin).status_code, 400)
                self.assertEqual(self.patch(bad, "approve").status_code, 400)
                self.assertEqual(self.patch(bad, "reject").status_code, 400)

    def test_15_already_approved_note_cannot_be_approved_again(self):
        note_id = self.add_note("pending")
        self.assertEqual(self.patch(note_id, "approve").status_code, 200)
        resp = self.patch(note_id, "approve")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already approved", resp.get_json()["error"])
        self.assertEqual(self.status_of(note_id), "approved")

    def test_16_already_rejected_note_cannot_be_rejected_again(self):
        note_id = self.add_note("pending")
        self.assertEqual(self.patch(note_id, "reject").status_code, 200)
        resp = self.patch(note_id, "reject")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already rejected", resp.get_json()["error"])
        self.assertEqual(self.status_of(note_id), "rejected")

    def test_16b_processed_notes_cannot_be_flipped(self):
        """Approved -> reject, rejected -> approve are refused too; nothing changes silently."""
        approved, rejected = self.add_note("approved"), self.add_note("rejected")
        self.assertEqual(self.patch(approved, "reject").status_code, 400)
        self.assertEqual(self.patch(rejected, "approve").status_code, 400)
        self.assertEqual(self.status_of(approved), "approved")
        self.assertEqual(self.status_of(rejected), "rejected")

    # ---- 17-18 and security: who may moderate ------------------------------------------

    def test_17_student_cannot_approve_note(self):
        note_id = self.add_note("pending")
        resp = self.patch(note_id, "approve", headers=self.student)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.status_of(note_id), "pending")

    def test_18_student_cannot_reject_note(self):
        note_id = self.add_note("pending")
        resp = self.patch(note_id, "reject", headers=self.student)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.status_of(note_id), "pending")

    def test_18b_students_cannot_use_any_admin_endpoint(self):
        note_id = self.add_note("pending")
        for method, url in (("get", f"/admin/notes/{note_id}"), ("get", f"/admin/notes/{note_id}/download")):
            self.assertEqual(getattr(self.client, method)(url, headers=self.student).status_code, 403)

    def test_18c_client_cannot_claim_to_be_admin(self):
        note_id = self.add_note("pending")
        attempts = [
            dict(headers={**self.student, "X-User-Role": "admin", "X-Role": "admin"}),
            dict(headers=self.student, query_string={"role": "admin", "is_admin": "1"}),
            dict(headers=self.student, json={"role": "admin", "user_id": 1}),
            dict(headers=self.student, data={"role": "admin"}),
        ]
        for kwargs in attempts:
            with self.subTest(kwargs=sorted(kwargs)):
                self.assertEqual(self.client.patch(f"/admin/notes/{note_id}/approve", **kwargs).status_code, 403)
                self.assertEqual(self.client.get("/admin/notes/pending", **kwargs).status_code, 403)
        self.assertEqual(self.status_of(note_id), "pending")

    def test_18d_role_in_token_is_checked_against_the_database(self):
        note_id = self.add_note("pending")
        # A correctly signed token that says "admin" for an account that is really a student.
        forged = {"Authorization": f"Bearer {auth.create_token(self.alice['id'], 'admin')}"}
        self.assertEqual(self.patch(note_id, "approve", headers=forged).status_code, 403)
        # ...and for an account that does not exist.
        ghost = {"Authorization": f"Bearer {auth.create_token(99999999, 'admin')}"}
        self.assertEqual(self.patch(note_id, "approve", headers=ghost).status_code, 401)
        # An admin account with a "student" token has no admin rights either.
        low = {"Authorization": f"Bearer {auth.create_token(1, 'student')}"}
        self.assertEqual(self.patch(note_id, "approve", headers=low).status_code, 403)
        self.assertEqual(self.status_of(note_id), "pending")

    def test_18e_students_cannot_change_roles(self):
        """There is no route that lets a client change a role; a register body cannot set one."""
        email = f"{PREFIX}sneaky-{self.tok}@example.com"
        resp = self.client.post("/register", json={"name": "S", "email": email, "password": PASSWORD, "role": "admin"})
        self.assertEqual(resp.status_code, 201)
        token = self.client.post("/login", json={"email": email, "password": PASSWORD}).get_json()
        self.assertEqual(token["role"], "student")

    # ---- 19: file safety ------------------------------------------------------------------

    def test_19_admin_download_cannot_escape_allowed_storage(self):
        outside = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        outside.write(SECRET_MARKER)
        outside.close()
        self.extra_files.append(__import__("pathlib").Path(outside.name))

        paths = [
            "../config.py", "seed_files/../config.py", "uploads/../app.py",
            "../../../../../../etc/passwd", "/etc/passwd", outside.name,
            "C:\\Windows\\win.ini", "..\\config.py", "seed_files/..%2fconfig.py",
            "uploads/", "uploads", "", "uploads/nope\x00.pdf", "seed_files/missing.pdf",
        ]
        link = UPLOADS / f"{PREFIX}{self.tok}-link.pdf"
        try:
            os.symlink(config.BASE_DIR / "config.py", link)
            self.extra_files.append(link)
            paths.append(f"uploads/{link.name}")
        except (OSError, NotImplementedError):
            pass  # symlinks unavailable (for example Windows without privileges)

        for path in paths:
            with self.subTest(file_path=path):
                note_id = self.add_note("pending", file_path=path)
                resp = self.client.get(f"/admin/notes/{note_id}/download", headers=self.admin)
                self.assertEqual(resp.status_code, 404)
                body = resp.get_data()
                resp.close()
                self.assertNotIn(SECRET_MARKER, body)
                self.assertNotIn(b"JWT_SECRET", body)
                self.assertNotIn(b"root:", body)
                self.assertEqual(resp.get_json(), {"error": "File not found"})

    def test_19b_missing_file_returns_404(self):
        note_id = self.add_note("pending", file_path=f"uploads/{PREFIX}{self.tok}-gone.pdf")
        resp = self.client.get(f"/admin/notes/{note_id}/download", headers=self.admin)
        self.assertEqual(resp.status_code, 404)

    def test_19c_file_of_one_note_cannot_be_reached_through_another_id(self):
        a = self.add_note("pending", content=pdf_bytes("A"))
        b = self.add_note("pending", content=pdf_bytes("B"))
        for note_id, expected in ((a, pdf_bytes("A")), (b, pdf_bytes("B"))):
            resp = self.client.get(f"/admin/notes/{note_id}/download", headers=self.admin)
            self.assertEqual(resp.get_data(), expected)
            resp.close()

    # ---- failures ----------------------------------------------------------------------------

    def test_20_failed_commit_rolls_back_and_changes_nothing(self):
        for action in ("approve", "reject"):
            with self.subTest(action=action):
                note_id = self.add_note("pending")
                broken = TrackingBrokenConnection(fail="commit")
                real_get = __import__("db").get_connection
                calls = {"n": 0}

                def get_connection():
                    calls["n"] += 1
                    # 1st call is the admin role check (real); 2nd is the moderation (broken).
                    return real_get() if calls["n"] == 1 else broken

                with patch("db.get_connection", side_effect=get_connection):
                    resp = self.patch(note_id, action)
                self.assertEqual(resp.status_code, 503)
                self.assertEqual(self.status_of(note_id), "pending")
                self.assertTrue(broken.closed)
                self.assertTrue(broken.rolled_back)

    # ---- full workflow ------------------------------------------------------------------------

    def upload_as_student(self, token, label):
        title = f"{PREFIX}{self.tok} {label}"
        content = pdf_bytes(label)
        resp = self.client.post(
            "/notes",
            data={"title": title, "description": "workflow test", "unit_id": "5",
                  "file": (io.BytesIO(content), "workflow.pdf", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"}, content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        rows, _ = run_sql("SELECT id FROM notes WHERE title = %s", (title,))
        return rows[0]["id"], title, content

    def test_21_full_approval_workflow(self):
        # student logs in (fresh login) and uploads
        login = self.client.post("/login", json={"email": self.bob["email"], "password": PASSWORD}).get_json()
        note_id, title, content = self.upload_as_student(login["token"], "approve flow")
        self.assertEqual(self.status_of(note_id), "pending")
        self.assert_hidden_from_students(note_id, title)

        # admin sees it, inspects it
        pending = self.admin_get("/admin/notes/pending").get_json()["notes"]
        mine = next(n for n in pending if n["id"] == note_id)
        self.assertEqual(mine["uploader_id"], self.bob["id"])
        self.assertEqual(self.admin_get(f"/admin/notes/{note_id}").get_json()["title"], title)
        resp = self.client.get(f"/admin/notes/{note_id}/download", headers=self.admin)
        self.assertEqual(resp.get_data(), content)
        resp.close()

        # admin approves; the student can now find and download it
        self.assertEqual(self.patch(note_id, "approve").get_json()["status"], "approved")
        self.assertEqual(self.status_of(note_id), "approved")
        self.assertIn(note_id, self.student_ids("/notes?q=" + PREFIX + self.tok))
        resp = self.client.get(f"/notes/{note_id}/download")
        self.assertEqual(resp.get_data(), content)
        resp.close()

    def test_22_full_rejection_workflow(self):
        note_id, title, _ = self.upload_as_student(self.bob["token"], "reject flow")
        self.assertEqual(self.patch(note_id, "reject").get_json()["status"], "rejected")
        self.assertEqual(self.status_of(note_id), "rejected")
        self.assert_hidden_from_students(note_id, title)


class RegressionTests(unittest.TestCase):
    """Re-run the earlier stages' test suites."""

    def run_suite(self, suite):
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        self.assertTrue(result.wasSuccessful(), stream.getvalue())
        return result.testsRun

    def test_23_stage3_auth_tests_still_pass(self):
        import test_auth
        self.assertGreater(self.run_suite(unittest.defaultTestLoader.loadTestsFromModule(test_auth)), 0)

    def test_24_stage4_browse_tests_still_pass(self):
        import test_browse
        self.assertGreater(self.run_suite(unittest.defaultTestLoader.loadTestsFromModule(test_browse)), 0)

    def test_25_stage5_notes_tests_still_pass(self):
        import test_notes
        self.assertGreater(self.run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(test_notes.NotesTests)), 0)

    def test_26_stage6_upload_tests_still_pass(self):
        import test_upload
        self.assertGreater(self.run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(test_upload.UploadTests)), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
