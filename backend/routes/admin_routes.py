"""Admin moderation routes: review, approve and reject uploaded notes.

Every route here requires a valid token whose role is 'admin'. The role is
never read from the request body, query string or any other client input:
it comes from the signed JWT and is then confirmed against the users table, so
a deleted or demoted account loses access immediately.

    GET   /admin/notes/pending           notes waiting for review
    GET   /admin/notes/<id>              metadata of one note (any status)
    GET   /admin/notes/<id>/download     the PDF, for review (any status)
    PATCH /admin/notes/<id>/approve      pending -> approved
    PATCH /admin/notes/<id>/reject       pending -> rejected

Errors are {"error": "..."}:
  400  bad note id, or the note is not pending any more
  401  missing/invalid token, or the account no longer exists
  403  the user is not an admin
  404  note not found, or its file is missing
  503  database problem (handled in app.py)

Student visibility is NOT implemented here. Students keep using the Stage 5
endpoints, which only ever return notes with status 'approved'.
"""
import logging
from functools import wraps

from flask import Blueprint, g, jsonify, send_file
from werkzeug.utils import secure_filename

import auth
import db
# Reuse the Stage 5 helpers so there is one implementation of id parsing and,
# above all, of safe file-path resolution.
from routes.notes_routes import _error, _parse_id, _safe_note_path

log = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Fixed SQL. Joins give the admin the subject and unit names; no user columns
# other than the uploader's id are selected, so no emails or hashes can leak.
ADMIN_NOTE_SELECT = """
    SELECT n.id, n.title, n.description, n.unit_id, n.uploader_id, n.file_type,
           n.status, n.created_at, n.download_count,
           s.name AS subject, u.title AS unit
    FROM notes n
    JOIN units u ON u.id = n.unit_id
    JOIN subjects s ON s.id = u.subject_id
"""


def admin_required(view):
    """Decorator: valid token + admin role (checked in the token AND the database)."""

    @auth.token_required
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = g.current_user
        if user["role"] != "admin":
            return _error("Admin access required", 403)

        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT role FROM users WHERE id = %s", (user["id"],))
                row = cur.fetchone()
        finally:
            conn.close()
        if row is None:
            return _error("Account no longer exists", 401)
        if row["role"] != "admin":
            return _error("Admin access required", 403)
        return view(*args, **kwargs)

    return wrapper


def _public(row):
    created = row["created_at"]
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "unit_id": row["unit_id"],
        "uploader_id": row["uploader_id"],
        "file_type": row["file_type"],
        "status": row["status"],
        "created_at": created.isoformat() if created else None,
        "download_count": row["download_count"],
        "subject": row["subject"],
        "unit": row["unit"],
        "file_url": f"/admin/notes/{row['id']}/download",
    }


def _rollback(conn):
    try:
        conn.rollback()
    except Exception:
        log.exception("Rollback failed")


def _fetch_note(note_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(ADMIN_NOTE_SELECT + " WHERE n.id = %s", (note_id,))
            return cur.fetchone()
    finally:
        conn.close()


@admin_bp.get("/notes/pending")
@admin_required
def list_pending():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Oldest first: the review queue is worked through in upload order.
            cur.execute(ADMIN_NOTE_SELECT + " WHERE n.status = 'pending' ORDER BY n.created_at, n.id")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"notes": [_public(r) for r in rows]})


@admin_bp.get("/notes/<note_id>")
@admin_required
def get_note(note_id):
    note_id = _parse_id(note_id)
    if note_id is None:
        return _error("Invalid note id", 400)
    row = _fetch_note(note_id)
    if row is None:
        return _error("Note not found", 404)
    return jsonify(_public(row))


@admin_bp.get("/notes/<note_id>/download")
@admin_required
def download_note(note_id):
    """Let an admin review the PDF of a note in any status.

    The admin sees exactly the files a student could see, no more: the stored
    path must resolve inside seed_files/ or uploads/ (see _safe_note_path).
    Reviewing is not a download by a student, so download_count is untouched.
    """
    note_id = _parse_id(note_id)
    if note_id is None:
        return _error("Invalid note id", 400)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT title, file_path FROM notes WHERE id = %s", (note_id,))
            note = cur.fetchone()
    finally:
        conn.close()

    if note is None:
        return _error("Note not found", 404)
    path = _safe_note_path(note["file_path"])
    if path is None:
        log.warning("Admin review: note %s file missing or outside allowed folders", note_id)
        return _error("File not found", 404)

    download_name = (secure_filename(note["title"]) or "note") + path.suffix
    return send_file(path, as_attachment=True, download_name=download_name, conditional=False)


def _moderate(note_id, new_status, message):
    """Move a note from 'pending' to new_status, atomically.

    One UPDATE ... WHERE status = 'pending' does the check and the change
    together, so two admins acting at the same moment cannot both succeed and an
    already processed note is never silently changed.
    """
    note_id = _parse_id(note_id)
    if note_id is None:
        return _error("Invalid note id", 400)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notes SET status = %s WHERE id = %s AND status = 'pending'",
                (new_status, note_id),
            )
            changed = cur.rowcount
            if not changed:
                cur.execute("SELECT status FROM notes WHERE id = %s", (note_id,))
                current = cur.fetchone()
        if not changed:
            _rollback(conn)
            if current is None:
                return _error("Note not found", 404)
            return _error(
                f"Note is already {current['status']}; only pending notes can be moderated", 400
            )
        conn.commit()
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.close()

    log.info("Admin %s set note %s to %s", g.current_user["id"], note_id, new_status)
    return jsonify({"message": message, "status": new_status})


@admin_bp.patch("/notes/<note_id>/approve")
@admin_required
def approve_note(note_id):
    return _moderate(note_id, "approved", "Note approved")


@admin_bp.patch("/notes/<note_id>/reject")
@admin_required
def reject_note(note_id):
    return _moderate(note_id, "rejected", "Note rejected")
