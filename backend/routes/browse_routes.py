"""Browse routes: Course -> Semester -> Subject -> Unit.

Public (no login) so the frontend can load the academic hierarchy easily.
Every route returns a plain JSON array. Errors are {"error": "..."}:
  400  query parameter missing or not a positive integer
  404  the parent record (course/semester/subject) does not exist
  503  database problem (handled in app.py)
An existing parent with no children returns 200 and [].
"""
import re

from flask import Blueprint, jsonify, request

import db

browse_bp = Blueprint("browse", __name__)

ID_RE = re.compile(r"[0-9]{1,10}")
MAX_ID = 4294967295  # largest value of INT UNSIGNED


def _error(message, status):
    return jsonify({"error": message}), status


def _parse_id(param):
    """Return (id, error_response) for a required positive-integer query parameter."""
    raw = request.args.get(param)
    if raw is None:
        return None, _error(f"Missing required query parameter: {param}", 400)
    if not ID_RE.fullmatch(raw) or not 0 < int(raw) <= MAX_ID:
        return None, _error(f"{param} must be a positive integer", 400)
    return int(raw), None


def _list_children(param, parent_label, exists_sql, list_sql):
    """Validate ?param=<id>, check the parent exists, then return the child rows."""
    parent_id, err = _parse_id(param)
    if err:
        return err

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(exists_sql, (parent_id,))
            if cur.fetchone() is None:
                return _error(f"{parent_label} not found", 404)
            cur.execute(list_sql, (parent_id,))
            rows = list(cur.fetchall())
    finally:
        conn.close()
    return jsonify(rows)


@browse_bp.get("/courses")
def get_courses():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM courses ORDER BY name")
            rows = list(cur.fetchall())
    finally:
        conn.close()
    return jsonify(rows)


@browse_bp.get("/semesters")
def get_semesters():
    return _list_children(
        "course_id",
        "Course",
        "SELECT 1 FROM courses WHERE id = %s",
        "SELECT id, number FROM semesters WHERE course_id = %s ORDER BY number",
    )


@browse_bp.get("/subjects")
def get_subjects():
    return _list_children(
        "semester_id",
        "Semester",
        "SELECT 1 FROM semesters WHERE id = %s",
        "SELECT id, name FROM subjects WHERE semester_id = %s ORDER BY name",
    )


@browse_bp.get("/units")
def get_units():
    # Ordered by id so units stay in syllabus order (Unit 1, Unit 2, ...).
    return _list_children(
        "subject_id",
        "Subject",
        "SELECT 1 FROM subjects WHERE id = %s",
        "SELECT id, title FROM units WHERE subject_id = %s ORDER BY id",
    )
