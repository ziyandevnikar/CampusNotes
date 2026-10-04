"""Notes routes: list/search/filter, detail, download and student upload.

Students only ever see notes whose status is 'approved'. Pending and rejected
notes behave exactly like notes that do not exist (404).

POST /notes lets a logged-in student upload a PDF. The note is created with
status 'pending' and stays hidden until an admin approves it (a later stage).

Errors are {"error": "..."}:
  400  bad q / subject_id / unit_id / note id, or an invalid upload
  401  upload without a valid token
  403  upload by someone who is not a student
  404  note not found, not approved, or its file is missing; unit not found
  413  uploaded file too large (handled in app.py)
  500  the uploaded file could not be written to disk
  503  database problem (handled in app.py)
"""
import logging
import re
import shutil
import uuid

from flask import Blueprint, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

import config
import db
from auth import token_required

log = logging.getLogger(__name__)

notes_bp = Blueprint("notes", __name__)

ID_RE = re.compile(r"[0-9]{1,10}")
MAX_ID = 4294967295  # largest value of INT UNSIGNED
MAX_QUERY_LENGTH = 100

# Upload limits. The title limit matches the VARCHAR(200) column; the
# description limit is a sensible cap for a TEXT column.
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
PDF_MAGIC = b"%PDF-"  # every real PDF starts with these bytes
# Content types a client may send for a PDF. Some tools send none or a generic
# one, so those are tolerated: the file's real bytes are checked as well.
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream", ""}

# Only files inside these folders can ever be served.
ALLOWED_DIRS = [config.SEED_FILES_DIR.resolve(), config.UPLOADS_DIR.resolve()]

# Fixed SQL: only approved notes, plus the subject name and unit title.
NOTE_SELECT = """
    SELECT n.id, n.title, n.description, s.name AS subject, u.title AS unit
    FROM notes n
    JOIN units u ON u.id = n.unit_id
    JOIN subjects s ON s.id = u.subject_id
    WHERE n.status = 'approved'
"""


def _error(message, status):
    return jsonify({"error": message}), status


def _parse_id(raw):
    """Return a positive int or None if raw is not a valid id."""
    if raw is None or not ID_RE.fullmatch(raw):
        return None
    value = int(raw)
    return value if 0 < value <= MAX_ID else None


def _like_pattern(word):
    """Build a LIKE pattern for a literal word ('!' is the escape character)."""
    for ch in ("!", "%", "_"):
        word = word.replace(ch, "!" + ch)
    return f"%{word}%"


def _public(row):
    """Shape a database row into the public API format."""
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "subject": row["subject"],
        "unit": row["unit"],
        "file_url": f"/notes/{row['id']}/download",
    }


def _safe_note_path(file_path):
    """Return the real Path of a note file, or None if it is missing or not allowed.

    The stored path is resolved (.. and symlinks followed) and must end up inside
    seed_files/ or uploads/ and be a regular file.
    """
    if not file_path or "\x00" in file_path:
        return None
    try:
        # Seed paths stay relative to backend/. Runtime upload paths are mapped
        # to the configured upload directory, which may be a persistent mount.
        if file_path == "uploads" or file_path.startswith("uploads/"):
            relative = file_path[len("uploads/"):] if file_path.startswith("uploads/") else ""
            candidate = (config.UPLOADS_DIR / relative).resolve()
        else:
            candidate = (config.BASE_DIR / file_path).resolve()
    except (OSError, ValueError):
        return None

    for allowed in ALLOWED_DIRS:
        if candidate.is_relative_to(allowed) and candidate.is_file():
            return candidate
    return None


@notes_bp.get("/notes")
def list_notes():
    sql = NOTE_SELECT
    params = []

    # Optional text search: every word must appear in the title or the description.
    q = request.args.get("q")
    if q is not None:
        q = q.strip()
        if len(q) > MAX_QUERY_LENGTH:
            return _error(f"q must be at most {MAX_QUERY_LENGTH} characters", 400)
        for word in q.split():
            pattern = _like_pattern(word)
            sql += " AND (n.title LIKE %s ESCAPE '!' OR n.description LIKE %s ESCAPE '!')"
            params += [pattern, pattern]

    # Optional filters.
    for param, column in (("subject_id", "s.id"), ("unit_id", "u.id")):
        raw = request.args.get(param)
        if raw is None:
            continue
        value = _parse_id(raw)
        if value is None:
            return _error(f"{param} must be a positive integer", 400)
        sql += f" AND {column} = %s"
        params.append(value)

    sql += " ORDER BY n.created_at DESC, n.id DESC"

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify([_public(r) for r in rows])


@notes_bp.get("/notes/<note_id>")
def get_note(note_id):
    note_id = _parse_id(note_id)
    if note_id is None:
        return _error("Invalid note id", 400)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(NOTE_SELECT + " AND n.id = %s", (note_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return _error("Note not found", 404)
    return jsonify(_public(row))


@notes_bp.get("/notes/<note_id>/download")
def download_note(note_id):
    note_id = _parse_id(note_id)
    if note_id is None:
        return _error("Invalid note id", 400)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, file_path FROM notes WHERE id = %s AND status = 'approved'",
                (note_id,),
            )
            note = cur.fetchone()
            if note is None:
                return _error("Note not found", 404)

            path = _safe_note_path(note["file_path"])
            if path is None:
                log.warning("Note %s: file missing or outside allowed folders", note_id)
                return _error("File not found", 404)

            # A HEAD request is not a download, so it is not counted.
            if request.method != "HEAD":
                cur.execute(
                    "UPDATE notes SET download_count = download_count + 1 WHERE id = %s",
                    (note_id,),
                )
                conn.commit()
    finally:
        conn.close()

    download_name = (secure_filename(note["title"]) or "note") + path.suffix
    return send_file(path, as_attachment=True, download_name=download_name, conditional=False)


# ---------------------------------------------------------------------------
# Student upload
# ---------------------------------------------------------------------------


def _check_pdf(upload):
    """Return (message, status) if the uploaded file is not acceptable, else None.

    Independent checks, because each one can be faked on its own: the file name
    ends in .pdf, the declared content type is not something else, and the first
    bytes really are a PDF header. The client's file name is only inspected
    here; it is never used to build a path.
    """
    if upload is None or not upload.filename:
        return "A PDF file is required (form field 'file')", 400
    if not secure_filename(upload.filename).lower().endswith(".pdf"):
        return "Only PDF files are allowed", 400
    if (upload.mimetype or "").lower() not in PDF_CONTENT_TYPES:
        return "Only PDF files are allowed", 400

    stream = upload.stream
    stream.seek(0, 2)  # jump to the end to measure the file
    size = stream.tell()
    stream.seek(0)
    if size == 0:
        return "The uploaded file is empty", 400
    if size > config.MAX_UPLOAD_BYTES:
        return f"File is too large (maximum {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB)", 413

    head = stream.read(len(PDF_MAGIC))
    stream.seek(0)
    if head != PDF_MAGIC:
        return "The uploaded file is not a valid PDF", 400
    return None


def _remove_file(path):
    """Delete a file we created. Never raises: this runs while handling another error."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        log.exception("Could not remove file %s", path)


def _save_upload(upload):
    """Write the upload into uploads/ under a random name.

    Returns (full_path, relative_path). The relative path (for example
    'uploads/3f2a....pdf') is what goes into notes.file_path. The name is a UUID
    chosen by the server, so uploads cannot collide or escape the folder.
    Raises OSError if the file cannot be written; nothing is left behind then.
    """
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.pdf"
    dest = config.UPLOADS_DIR / name

    # Mode "x" fails instead of overwriting if the file somehow already exists.
    # If open() fails we created nothing, so there is nothing to clean up.
    out = open(dest, "xb")
    try:
        with out:
            shutil.copyfileobj(upload.stream, out)
    except BaseException:
        _remove_file(dest)
        raise
    return dest, f"uploads/{name}"


@notes_bp.post("/notes")
@token_required
def upload_note():
    # The uploader always comes from the verified token, never from the request.
    user = g.current_user
    if user["role"] != "student":
        return _error("Only students can upload notes", 403)

    if request.mimetype != "multipart/form-data":
        return _error("Request must be multipart/form-data", 400)

    title = (request.form.get("title") or "").strip()
    if not title:
        return _error("title is required", 400)
    if len(title) > MAX_TITLE_LENGTH:
        return _error(f"title must be at most {MAX_TITLE_LENGTH} characters", 400)

    description = (request.form.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return _error(f"description must be at most {MAX_DESCRIPTION_LENGTH} characters", 400)

    raw_unit_id = request.form.get("unit_id")
    if raw_unit_id is None:
        return _error("unit_id is required", 400)
    unit_id = _parse_id(raw_unit_id)
    if unit_id is None:
        return _error("unit_id must be a positive integer", 400)

    upload = request.files.get("file")
    problem = _check_pdf(upload)
    if problem:
        return _error(*problem)

    saved = None
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM units WHERE id = %s", (unit_id,))
            if cur.fetchone() is None:
                return _error("Unit not found", 404)

            # Save the file first: if that fails no database row is created.
            try:
                saved, file_path = _save_upload(upload)
            except OSError:
                log.exception("Could not save uploaded file")
                return _error("Could not save the uploaded file", 500)

            cur.execute(
                "INSERT INTO notes "
                "(title, description, unit_id, uploader_id, file_path, file_type, status, "
                "created_at, download_count) "
                "VALUES (%s, %s, %s, %s, %s, 'pdf', 'pending', NOW(), 0)",
                (title, description or None, unit_id, user["id"], file_path),
            )
        conn.commit()
    except Exception:
        # The insert or commit failed after the file was written: remove the
        # file so no orphan is left behind, then let app.py report the error.
        if saved is not None:
            _remove_file(saved)
        raise
    finally:
        conn.close()

    log.info("User %s uploaded a note for unit %s (pending approval)", user["id"], unit_id)
    return jsonify({"message": "Note uploaded for approval", "status": "pending"}), 201
