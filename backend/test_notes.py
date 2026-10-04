"""Notes API tests (list, search, filters, detail, download). Needs MySQL with init.sql loaded.

    export DB_PASSWORD="your-mysql-password"
    python test_notes.py

Uses Flask's test client. The tests create their own temporary notes (title starts
with 'notestest-') and temporary PDF files in seed_files/ and uploads/, and remove
them afterwards. Permanent seed notes are only read, never changed. The last test
class re-runs the Stage 3 (auth) and Stage 4 (browse) test suites.
"""
import io
import os
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")

import pymysql

import config
import db
from app import app

PREFIX = "notestest-"
PUBLIC_KEYS = {"id", "title", "description", "subject", "unit", "file_url"}


def run_sql(sql, args=(), commit=False):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
            last_id = getattr(cur, "lastrowid", None)
        if commit:
            conn.commit()
        return rows, last_id
    finally:
        conn.close()


def delete_test_notes():
    run_sql("DELETE FROM notes WHERE title LIKE %s", (PREFIX + "%",), commit=True)


def pdf_bytes(tag):
    return b"%PDF-1.4\n% " + tag.encode() + b"\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


class NotesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.tok = uuid.uuid4().hex[:8]
        cls.files = []
        delete_test_notes()

        tok = cls.tok
        # Real temporary files: one under seed_files/, one under uploads/.
        a_path, b_path = f"seed_files/{PREFIX}{tok}-a.pdf", f"uploads/{PREFIX}{tok}-b.pdf"
        cls.pdf_a, cls.pdf_b = pdf_bytes("A" + tok), pdf_bytes("B" + tok)
        for rel, data in ((a_path, cls.pdf_a), (b_path, cls.pdf_b)):
            full = config.BASE_DIR / rel
            full.write_bytes(data)
            cls.files.append(full)

        cls.a = cls.add(f"{PREFIX}{tok} Stack Primer", "Plain text alpha", 5, a_path, "approved")
        cls.b = cls.add(f"{PREFIX}{tok} Joins Primer", f"Covers marker{tok}gamma topic", 7, b_path, "approved")
        cls.pending = cls.add(f"{PREFIX}{tok} Stack Pending", "pending note", 5, a_path, "pending")
        cls.rejected = cls.add(f"{PREFIX}{tok} Stack Rejected", "rejected note", 5, a_path, "rejected")
        cls.missing = cls.add(f"{PREFIX}{tok} Missing File", "file not on disk", 5,
                              f"uploads/{PREFIX}{tok}-missing.pdf", "approved")

        # Rows whose stored file_path tries to escape the allowed folders.
        cls.evil = [
            cls.add(f"{PREFIX}{tok} Evil {i}", "traversal", 5, path, "approved")
            for i, path in enumerate([
                "../config.py",
                "seed_files/../config.py",
                "uploads/../app.py",
                "../../../../../../etc/passwd",
                "/etc/passwd",
                "seed_files/..%2fconfig.py",
            ])
        ]

        # A symlink inside uploads/ that points outside the allowed folders.
        link = config.BASE_DIR / f"uploads/{PREFIX}{tok}-link.pdf"
        cls.link_note = None
        try:
            os.symlink(config.BASE_DIR / "config.py", link)
            cls.files.append(link)
            cls.link_note = cls.add(f"{PREFIX}{tok} Symlink", "symlink", 5, f"uploads/{PREFIX}{tok}-link.pdf", "approved")
        except (OSError, NotImplementedError):
            pass  # symlinks not available (for example on Windows without privileges)

    @classmethod
    def tearDownClass(cls):
        delete_test_notes()
        for f in cls.files:
            try:
                f.unlink()
            except FileNotFoundError:
                pass

    @classmethod
    def add(cls, title, description, unit_id, file_path, status):
        _, new_id = run_sql(
            "INSERT INTO notes (title, description, unit_id, uploader_id, file_path, status) "
            "VALUES (%s, %s, %s, 1, %s, %s)",
            (title, description, unit_id, file_path, status),
            commit=True,
        )
        return new_id

    # helpers
    def get(self, url, status=200):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status, resp.get_data(as_text=True)[:300])
        resp.close()  # release the file handle (matters on Windows when deleting temp files)
        return resp

    def ids(self, url):
        return [n["id"] for n in self.get(url).get_json()]

    def count(self, note_id):
        rows, _ = run_sql("SELECT download_count FROM notes WHERE id = %s", (note_id,))
        return rows[0]["download_count"]

    # ---- list ----------------------------------------------------------

    def test_01_list_returns_approved_notes_in_public_format(self):
        notes = self.get("/notes").get_json()
        titles = {n["title"] for n in notes}
        for expected in ("Linked List Complete Notes", "Stack and Queue Quick Revision", "SQL Joins Cheat Sheet"):
            self.assertIn(expected, titles)
        self.assertIn(self.a, [n["id"] for n in notes])
        for n in notes:  # no database internals leak
            self.assertEqual(set(n), PUBLIC_KEYS)
            self.assertEqual(n["file_url"], f"/notes/{n['id']}/download")

    def test_02_pending_notes_are_not_returned(self):
        notes = self.get("/notes").get_json()
        self.assertNotIn("ER Model Handwritten Notes", {n["title"] for n in notes})
        self.assertNotIn(self.pending, [n["id"] for n in notes])
        self.assertNotIn(self.pending, self.ids(f"/notes?q={self.tok}"))

    def test_03_rejected_notes_are_not_returned(self):
        notes = self.get("/notes").get_json()
        self.assertNotIn("C Loops Practice Questions", {n["title"] for n in notes})
        self.assertNotIn(self.rejected, [n["id"] for n in notes])
        self.assertNotIn(self.rejected, self.ids(f"/notes?q={self.tok}"))

    # ---- search --------------------------------------------------------

    def test_04_search_by_title(self):
        self.assertEqual(self.ids(f"/notes?q={self.tok} stack"), [self.a])
        self.assertEqual(self.ids(f"/notes?q={self.tok}%20STACK%20primer"), [self.a])  # any case, several words
        seed = [n["title"] for n in self.get("/notes?q=linked").get_json()]
        self.assertIn("Linked List Complete Notes", seed)

    def test_05_search_by_description(self):
        self.assertEqual(self.ids(f"/notes?q=marker{self.tok}gamma"), [self.b])

    def test_05b_search_edge_cases(self):
        self.assertEqual(self.get("/notes?q=%25").get_json(), [])      # '%' is literal, not a wildcard
        self.assertEqual(self.get("/notes?q=_").get_json(), [])        # so is '_'
        self.assertEqual(self.get("/notes?q=%27%20OR%201%3D1%20--").get_json(), [])  # SQL injection text
        self.assertEqual(self.ids("/notes?q=%20%20"), self.ids("/notes"))  # blank q = no search
        body = self.get("/notes?q=" + "x" * 101, status=400).get_json()
        self.assertIn("q", body["error"])

    # ---- filters -------------------------------------------------------

    def test_06_subject_id_filter(self):
        notes = self.get("/notes?subject_id=3").get_json()
        self.assertTrue(notes)
        self.assertEqual({n["subject"] for n in notes}, {"Data Structures"})
        ids = [n["id"] for n in notes]
        self.assertIn(self.a, ids)
        self.assertNotIn(self.b, ids)  # DBMS note

    def test_07_unit_id_filter(self):
        notes = self.get("/notes?unit_id=5").get_json()
        self.assertEqual({n["unit"] for n in notes}, {"Unit 2: Stacks and Queues"})
        self.assertIn(self.a, [n["id"] for n in notes])
        self.assertEqual(self.ids(f"/notes?unit_id=7&q={self.tok}"), [self.b])
        self.assertEqual(self.get("/notes?unit_id=999999").get_json(), [])

    def test_08_search_and_filters_combine(self):
        t = self.tok
        self.assertEqual(self.ids(f"/notes?q={t} primer&subject_id=3&unit_id=5"), [self.a])
        self.assertEqual(self.ids(f"/notes?q={t} primer&subject_id=4&unit_id=7"), [self.b])
        self.assertEqual(self.ids(f"/notes?q={t} primer&subject_id=4"), [self.b])
        self.assertEqual(self.get(f"/notes?q={t} primer&subject_id=4&unit_id=5").get_json(), [])  # unit not in subject

    def test_08b_invalid_filters_return_400(self):
        for url in ["/notes?subject_id=abc", "/notes?unit_id=0", "/notes?unit_id=-1",
                    "/notes?subject_id=1.5", "/notes?unit_id=", "/notes?subject_id=4294967296"]:
            with self.subTest(url=url):
                self.assertIn("error", self.get(url, status=400).get_json())

    # ---- detail --------------------------------------------------------

    def test_09_detail_returns_approved_note(self):
        note = self.get(f"/notes/{self.a}").get_json()
        self.assertEqual(note, {
            "id": self.a,
            "title": f"{PREFIX}{self.tok} Stack Primer",
            "description": "Plain text alpha",
            "subject": "Data Structures",
            "unit": "Unit 2: Stacks and Queues",
            "file_url": f"/notes/{self.a}/download",
        })

    def test_10_pending_and_rejected_detail_is_404(self):
        for note_id in (self.pending, self.rejected):
            with self.subTest(note_id=note_id):
                self.assertEqual(self.get(f"/notes/{note_id}", status=404).get_json(), {"error": "Note not found"})

    def test_11_unknown_and_invalid_note_ids(self):
        self.assertEqual(self.get("/notes/99999999", status=404).get_json(), {"error": "Note not found"})
        for bad in ["abc", "0", "-1", "1.5", "4294967296", "1%20OR%201=1"]:
            with self.subTest(bad=bad):
                self.assertEqual(self.get(f"/notes/{bad}", status=400).get_json(), {"error": "Invalid note id"})
                self.assertEqual(self.get(f"/notes/{bad}/download", status=400).get_json(), {"error": "Invalid note id"})

    # ---- download ------------------------------------------------------

    def test_12_approved_pdf_download_works(self):
        for note_id, data in ((self.a, self.pdf_a), (self.b, self.pdf_b)):  # seed_files/ and uploads/
            with self.subTest(note_id=note_id):
                resp = self.get(f"/notes/{note_id}/download")
                self.assertEqual(resp.mimetype, "application/pdf")
                self.assertEqual(resp.data, data)
                self.assertIn("attachment", resp.headers["Content-Disposition"])
                self.assertIn(".pdf", resp.headers["Content-Disposition"])

    def test_13_missing_file_returns_404(self):
        self.assertEqual(self.get(f"/notes/{self.missing}/download", status=404).get_json(), {"error": "File not found"})

    def test_13b_pending_and_rejected_cannot_be_downloaded(self):
        for note_id in (self.pending, self.rejected):
            self.assertEqual(self.get(f"/notes/{note_id}/download", status=404).get_json(), {"error": "Note not found"})
            self.assertEqual(self.count(note_id), 0)

    def test_14_download_increments_download_count(self):
        before = self.count(self.b)
        self.get(f"/notes/{self.b}/download")
        self.assertEqual(self.count(self.b), before + 1)
        self.get(f"/notes/{self.b}/download")
        self.assertEqual(self.count(self.b), before + 2)

    def test_14b_failed_downloads_and_head_do_not_count(self):
        before = self.count(self.a)
        head = self.client.head(f"/notes/{self.a}/download")
        head.close()
        self.assertEqual(head.status_code, 200)
        self.assertEqual(self.count(self.a), before)
        self.get(f"/notes/{self.missing}/download", status=404)
        self.assertEqual(self.count(self.missing), 0)

    def test_15_path_traversal_cannot_read_other_files(self):
        secret_marker = b"JWT_SECRET"  # appears in config.py
        for note_id in self.evil:
            with self.subTest(note_id=note_id):
                resp = self.client.get(f"/notes/{note_id}/download")
                self.assertEqual(resp.status_code, 404)
                self.assertNotIn(secret_marker, resp.data)
                self.assertEqual(self.count(note_id), 0)
        if self.link_note:
            resp = self.client.get(f"/notes/{self.link_note}/download")
            self.assertEqual(resp.status_code, 404)
            self.assertNotIn(secret_marker, resp.data)

    def test_15b_traversal_in_the_url_does_not_reach_the_route(self):
        for url in ["/notes/../config.py/download", "/notes/..%2fconfig.py/download", "/notes/1/download/../../config.py"]:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertIn(resp.status_code, (400, 404))
                self.assertNotIn(b"JWT_SECRET", resp.data)

    # ---- database failure ---------------------------------------------

    def test_16_database_failure_returns_503(self):
        error = pymysql.err.OperationalError(2003, "Can't connect to MySQL server")
        with patch("db.get_connection", side_effect=error):
            for url in ("/notes", "/notes?q=stack", f"/notes/{self.a}", f"/notes/{self.a}/download"):
                with self.subTest(url=url):
                    resp = self.client.get(url)
                    self.assertEqual(resp.status_code, 503)
                    self.assertEqual(resp.get_json(), {"error": "Database unavailable"})
        self.assertEqual(self.client.get("/ping").status_code, 200)  # app still alive

    def test_16b_query_error_returns_503_and_closes_connection(self):
        class BrokenConnection:
            closed = False

            def cursor(self):
                raise pymysql.err.ProgrammingError(1146, "Table doesn't exist")

            def close(self):
                self.closed = True

        broken = BrokenConnection()
        with patch("db.get_connection", return_value=broken):
            resp = self.client.get("/notes")
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(broken.closed)


class RegressionTests(unittest.TestCase):
    """Re-run the earlier stages' test suites."""

    def run_suite(self, module_name):
        module = __import__(module_name)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        self.assertTrue(result.wasSuccessful(), stream.getvalue())
        return result.testsRun

    def test_17_stage3_auth_tests_still_pass(self):
        self.assertGreater(self.run_suite("test_auth"), 0)

    def test_18_stage4_browse_tests_still_pass(self):
        self.assertGreater(self.run_suite("test_browse"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
