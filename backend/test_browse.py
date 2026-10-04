"""Browse API tests. Needs MySQL running with init.sql loaded.

    export DB_PASSWORD="your-mysql-password"
    python test_browse.py

Uses Flask's test client (the server does not need to be running). The tests
expect the seed data from init.sql. One temporary course ('browsetest-...')
is created to test "parent exists but has no children" and is deleted afterwards.
"""
import os
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")

import pymysql

import db
from app import app

TEMP_PREFIX = "browsetest-"


def delete_temp_courses():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM courses WHERE name LIKE %s", (TEMP_PREFIX + "%",))
        conn.commit()
    finally:
        conn.close()


class BrowseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        delete_temp_courses()

    @classmethod
    def tearDownClass(cls):
        delete_temp_courses()

    def get_json(self, url, status=200):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status, resp.get_data(as_text=True))
        self.assertTrue(resp.is_json)
        return resp.get_json()

    # ---- happy paths -------------------------------------------------

    def test_01_courses_returns_courses(self):
        courses = self.get_json("/courses")
        self.assertEqual(courses, [{"id": 1, "name": "BCA"}])

    def test_02_semesters_for_course(self):
        semesters = self.get_json("/semesters?course_id=1")
        self.assertEqual([s["number"] for s in semesters], [1, 2])
        for s in semesters:
            self.assertEqual(set(s), {"id", "number"})

    def test_03_subjects_for_semester_are_scoped_to_that_semester(self):
        sem1 = {s["id"]: s["number"] for s in self.get_json("/semesters?course_id=1")}
        first = [i for i, n in sem1.items() if n == 1][0]
        second = [i for i, n in sem1.items() if n == 2][0]

        names1 = [s["name"] for s in self.get_json(f"/subjects?semester_id={first}")]
        names2 = [s["name"] for s in self.get_json(f"/subjects?semester_id={second}")]
        self.assertEqual(names1, ["Computer Fundamentals", "Programming in C"])
        self.assertEqual(names2, ["Data Structures", "Database Management Systems"])
        for s in self.get_json(f"/subjects?semester_id={first}"):
            self.assertEqual(set(s), {"id", "name"})

    def test_04_units_for_subject_are_scoped_to_that_subject(self):
        subjects = {s["name"]: s["id"] for s in self.get_json("/subjects?semester_id=2")}
        ds_units = self.get_json(f"/units?subject_id={subjects['Data Structures']}")
        dbms_units = self.get_json(f"/units?subject_id={subjects['Database Management Systems']}")
        self.assertEqual(
            [u["title"] for u in ds_units],
            ["Unit 1: Arrays and Linked Lists", "Unit 2: Stacks and Queues"],
        )
        self.assertEqual(
            [u["title"] for u in dbms_units],
            ["Unit 1: Introduction to DBMS and ER Model", "Unit 2: SQL Basics"],
        )
        for u in ds_units:
            self.assertEqual(set(u), {"id", "title"})

    def test_05_full_hierarchy_can_be_walked(self):
        """Acceptance: Course -> Semester -> Subject -> Unit through the API."""
        course = self.get_json("/courses")[0]
        semester = self.get_json(f"/semesters?course_id={course['id']}")[0]
        subject = self.get_json(f"/subjects?semester_id={semester['id']}")[0]
        units = self.get_json(f"/units?subject_id={subject['id']}")
        self.assertTrue(units)

    def test_06_browsing_needs_no_login(self):
        # No Authorization header is sent anywhere in this class; this makes it explicit.
        self.assertEqual(self.client.get("/courses").status_code, 200)

    def test_07_parent_without_children_returns_empty_list(self):
        name = TEMP_PREFIX + uuid.uuid4().hex[:8]
        self.addCleanup(delete_temp_courses)  # remove it right after this test
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO courses (name) VALUES (%s)", (name,))
                cur.execute("SELECT id FROM courses WHERE name = %s", (name,))
                course_id = cur.fetchone()["id"]
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.get_json(f"/semesters?course_id={course_id}"), [])

    # ---- missing / invalid parameters --------------------------------

    def test_08_missing_course_id(self):
        body = self.get_json("/semesters", status=400)
        self.assertIn("course_id", body["error"])

    def test_09_missing_semester_id(self):
        body = self.get_json("/subjects", status=400)
        self.assertIn("semester_id", body["error"])

    def test_10_missing_subject_id(self):
        body = self.get_json("/units", status=400)
        self.assertIn("subject_id", body["error"])

    def test_11_invalid_ids_are_rejected_with_400(self):
        bad_values = ["abc", "0", "-1", "1.5", "", " 1", "1 ", "+1", "1e3",
                      "99999999999999999999", "4294967296", "1;DROP TABLE courses"]
        for path, param in [("/semesters", "course_id"), ("/subjects", "semester_id"), ("/units", "subject_id")]:
            for value in bad_values:
                with self.subTest(path=path, value=value):
                    resp = self.client.get(path, query_string={param: value})
                    self.assertEqual(resp.status_code, 400)
                    self.assertIn("error", resp.get_json())

    def test_12_sql_injection_attempt_does_nothing(self):
        self.client.get("/semesters", query_string={"course_id": "1; DROP TABLE courses"})
        self.client.get("/semesters", query_string={"course_id": "1 OR 1=1"})
        self.assertEqual(self.get_json("/courses"), [{"id": 1, "name": "BCA"}])

    def test_13_nonexistent_ids_return_404(self):
        for path, param, label in [
            ("/semesters", "course_id", "Course"),
            ("/subjects", "semester_id", "Semester"),
            ("/units", "subject_id", "Subject"),
        ]:
            with self.subTest(path=path):
                body = self.get_json(f"{path}?{param}=999999", status=404)
                self.assertEqual(body, {"error": f"{label} not found"})

    # ---- database errors ---------------------------------------------

    def test_14_cannot_connect_to_database_returns_503(self):
        error = pymysql.err.OperationalError(2003, "Can't connect to MySQL server")
        endpoints = ["/courses", "/semesters?course_id=1", "/subjects?semester_id=1", "/units?subject_id=1"]
        with patch("db.get_connection", side_effect=error):
            for url in endpoints:
                with self.subTest(url=url):
                    resp = self.client.get(url)
                    self.assertEqual(resp.status_code, 503)
                    self.assertEqual(resp.get_json(), {"error": "Database unavailable"})

    def test_15_query_error_returns_503_and_closes_connection(self):
        class BrokenConnection:
            closed = False

            def cursor(self):
                raise pymysql.err.ProgrammingError(1146, "Table doesn't exist")

            def close(self):
                self.closed = True

        broken = BrokenConnection()
        with patch("db.get_connection", return_value=broken):
            resp = self.client.get("/courses")
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(broken.closed)

    def test_16_app_keeps_working_after_database_errors(self):
        with patch("db.get_connection", side_effect=pymysql.err.OperationalError(2003, "down")):
            self.assertEqual(self.client.get("/courses").status_code, 503)
        self.assertEqual(self.client.get("/ping").status_code, 200)
        self.assertEqual(self.client.get("/courses").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
