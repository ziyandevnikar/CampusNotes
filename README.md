# CampusNotes

**Centralized Academic Notes Platform**

## What CampusNotes does

Students today find study material scattered across WhatsApp groups, Telegram groups, Drive links and personal chats. CampusNotes puts it in one place, organised the way a college is organised:

Course → Semester → Subject → Unit → Notes

Students can browse, search, preview and download notes, and contribute their own. Uploaded notes are reviewed by an admin before they become visible to other students.

> Current status: **Final (Stage 10) - deployment ready, not live.** Complete web app: Flask API (auth, browse, notes/search/download, student upload, admin moderation), MySQL schema with seed data and demo PDFs, and an Angular frontend for students and admins. See `docs/FINAL_QA_REPORT.md` for exactly what was and was not verified.

## Technology

| Layer    | Technology              |
|----------|-------------------------|
| Frontend | Angular                 |
| Backend  | Python Flask, Flask-CORS|
| Database | MySQL 8 via PyMySQL (no ORM) |

## Prerequisites

- Python 3.10+
- Node.js 18.19+ (or 20.11+ / 22+) and npm

## Run locally on Windows (demo)

The following commands use the installed MySQL 8.4 server and keep its data
under the current Windows user profile, so initializing MySQL does not require
administrator access. If the MySQL data directory already exists, do not
initialize it again.

Open PowerShell in the project root. Initialize a fresh, user-owned data
directory once:

```powershell
$mysqlHome = 'C:\Program Files\MySQL\MySQL Server 8.4'
$dataDir = Join-Path $env:LOCALAPPDATA 'CampusNotes\mysql\data'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
& "$mysqlHome\bin\mysqld.exe" --initialize-insecure "--basedir=$mysqlHome" "--datadir=$dataDir" --console
```

`--initialize-insecure` creates a local MySQL root account with no password.
The server below is explicitly bound to loopback; use this only for a local
demo and never expose it to a network or use it in production.

Start MySQL in its own PowerShell window and leave that window open:

```powershell
$mysqlHome = 'C:\Program Files\MySQL\MySQL Server 8.4'
$dataDir = Join-Path $env:LOCALAPPDATA 'CampusNotes\mysql\data'
& "$mysqlHome\bin\mysqld.exe" --console "--basedir=$mysqlHome" "--datadir=$dataDir" --bind-address=127.0.0.1 --port=3306 --mysqlx=0
```

In another PowerShell window at the project root, load the existing schema and
demo data once:

```powershell
$mysqlHome = 'C:\Program Files\MySQL\MySQL Server 8.4'
$schema = (Resolve-Path .\backend\init.sql).Path.Replace('\', '/')
& "$mysqlHome\bin\mysql.exe" --protocol=TCP --host=127.0.0.1 --port=3306 --user=root --execute="source $schema"
```

**Warning:** `init.sql` drops and recreates the CampusNotes tables. Run it only
for a fresh local demo database; it resets all CampusNotes data.

Start Flask in a third PowerShell window:

```powershell
Set-Location .\backend
$env:DATABASE_HOST = '127.0.0.1'
$env:DATABASE_PORT = '3306'
$env:DATABASE_USER = 'root'
$env:DATABASE_PASSWORD = ''
$env:JWT_SECRET = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
python .\app.py
```

Install frontend packages once, then start Angular in a fourth window:

```powershell
Set-Location .\frontend
npm.cmd install
npm.cmd start
```

Open `http://localhost:4200`. The development Angular environment already
targets Flask at `http://127.0.0.1:5000`; local CORS already allows
`http://localhost:4200`. Demo credentials are listed in `backend/init.sql`.

## Local setup and production deployment

CampusNotes is prepared as a hosting-neutral production application with this target architecture:

```text
Angular frontend
      ↓
Production Flask API (WSGI)
      ↓
Production MySQL 8+
      ↓
Persistent file storage
```

No hosting provider is assumed because Stage 8 did not specify one. The host must support an Angular static frontend, a Python/Flask WSGI backend, MySQL 8+, HTTPS, environment variables/secrets, and **persistent storage for runtime PDF uploads**.

### Requirements

- Python 3.10+
- Node.js 18.19+ (or 20.11+ / 22+) and npm
- MySQL 8+
- A production WSGI server such as Gunicorn on Linux/Unix hosting
- HTTPS at the deployed frontend/API origins
- Persistent storage for `UPLOAD_DIRECTORY`

### Environment variables

Copy `backend/.env.example` into your deployment platform's environment configuration. The application does not automatically load `.env` files.

| Variable | Required | Purpose |
|---|---|---|
| `FLASK_ENV` | Production: yes | Set to `production` |
| `FLASK_DEBUG` | No | Keep `0` in production |
| `DATABASE_HOST` | Yes | MySQL host |
| `DATABASE_PORT` | Yes | MySQL port, normally `3306` |
| `DATABASE_NAME` | Yes | `campusnotes` |
| `DATABASE_USER` | Yes | Dedicated application DB user |
| `DATABASE_PASSWORD` | Yes | MySQL password |
| `JWT_SECRET` | Yes | Strong random signing secret |
| `JWT_EXPIRY_HOURS` | No | JWT lifetime; default `24` |
| `CORS_ALLOWED_ORIGINS` | Production: yes | Comma-separated deployed frontend origin(s) |
| `UPLOAD_DIRECTORY` | No | Persistent upload directory; defaults to `backend/uploads` |

Legacy `DB_*` names remain accepted for existing Stage 8 local tests, but production configuration should use the `DATABASE_*` names above.

### Database setup

Create the production database and import the schema/seed data from `backend/init.sql` **only for a new demo/initial database**:

```bash
mysql -u root -p < backend/init.sql
```

`init.sql` drops and recreates CampusNotes tables, so do **not** run it against an existing production database that contains real data. For a real deployment, migrate/import the required tables (`users`, `courses`, `semesters`, `subjects`, `units`, `notes`) without destroying existing data.

Create a dedicated MySQL application user rather than using `root`.

### Backend installation

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

### Backend start command

For a Linux/Unix production host:

```bash
cd backend
gunicorn -c gunicorn.conf.py wsgi:app
```

Do **not** use `python app.py` / Flask's development server as the production server.

### Health check

After the API starts:

```text
GET /ping
```

Expected response:

```json
{"message":"CampusNotes API is running"}
```

The endpoint intentionally exposes no database credentials or internal information.

### Frontend production API URL

Edit `frontend/src/environments/environment.prod.ts` before building:

```ts
export const environment = {
  production: true,
  apiUrl: 'https://your-real-api-origin.example.com',
};
```

Then:

```bash
cd frontend
npm install
npm run build
```

The production build is emitted to:

```text
frontend/dist/campusnotes-frontend/
```

Deploy that directory to an HTTPS static web host. The Angular production configuration does not contain the development `127.0.0.1:5000` API URL.

### CORS

Set `CORS_ALLOWED_ORIGINS` to the exact deployed frontend origin, for example:

```text
CORS_ALLOWED_ORIGINS=https://campusnotes.example.com
```

Do not use `*` in production. Local development keeps its localhost CORS default.

### File storage

Student uploads are stored under `UPLOAD_DIRECTORY` with server-generated UUID filenames. The database stores logical `uploads/<uuid>.pdf` paths.

**Important:** local disk is not automatically persistent on every hosting platform. Before going live, confirm that the directory supplied through `UPLOAD_DIRECTORY` survives application restart/redeploy. If the selected host has an ephemeral filesystem and no persistent disk, runtime PDF storage is a deployment blocker. No paid storage service has been added by Stage 9.

`backend/seed_files/` contains demo PDFs and is part of the application package. `backend/uploads/` contains only `.gitkeep` in the repository; runtime student uploads must never be committed.

### Security notes

- Keep `.env` and all real secrets outside source control.
- Use a strong random `JWT_SECRET`.
- Keep Flask debug mode disabled in production.
- Never put database credentials or JWT secrets in Angular source.
- Backend permissions remain enforced server-side; frontend route guards are not security boundaries.
- Uploaded filenames are not used as filesystem paths.
- Uploaded PDFs require a `.pdf` name, acceptable content type, and `%PDF-` header.
- Files are served only from the configured seed/upload directories.
- Admin endpoints require an authenticated admin token.
- Passwords continue to use Werkzeug password hashing.
- Production error responses are JSON and do not expose stack traces, filesystem paths, or credentials.
- Use HTTPS for the deployed frontend and API.

### Production smoke test

If a real deployment is available, verify:

```text
GET /ping
→ Frontend loads
→ Register
→ Login
→ Browse
→ Search
→ Download
→ Upload
→ Admin login
→ Approve
→ Student sees approved note
→ Reject another pending note
```

If no host/deployment credentials are available, this Stage 9 package must be treated as **deployment-ready preparation, not a live deployment**. The remaining manual step is selecting/configuring a host and supplying its production MySQL, HTTPS, CORS, secrets, and persistent-storage settings.

## Authentication API

- `POST /register` with `{name, email, password}` creates a student account (`201`).
- `POST /login` with `{email, password}` returns `{token, role}`.
- Send the token on protected routes (added in later stages) as `Authorization: Bearer <token>`.

Errors are returned as `{"error": "..."}` with status 400 (bad input), 401 (bad login or token) or 409 (duplicate email).

## Browse API

Public endpoints (no login needed). Each returns a JSON array.

| Endpoint | Returns |
|---|---|
| `GET /courses` | `[{"id", "name"}]` |
| `GET /semesters?course_id=1` | `[{"id", "number"}]` |
| `GET /subjects?semester_id=1` | `[{"id", "name"}]` |
| `GET /units?subject_id=1` | `[{"id", "title"}]` |

A missing or non-integer id returns 400, an id that does not exist returns 404, and a parent with no children returns `[]`. Errors look like `{"error": "..."}`.

## Notes API

Public endpoints. Only notes with status `approved` are ever returned; pending and rejected notes behave as if they do not exist (404).

| Endpoint | Returns |
|---|---|
| `GET /notes` | list of notes, newest first |
| `GET /notes?q=stack&subject_id=3&unit_id=5` | same, filtered. All parameters are optional and combine |
| `GET /notes/<id>` | one note |
| `GET /notes/<id>/download` | the PDF file; increases `download_count` |

Each note looks like `{"id", "title", "description", "subject", "unit", "file_url"}`. `q` matches words in the title or description (every word must match, any case, max 100 characters). Errors look like `{"error": "..."}`: 400 for bad input, 404 for a missing/unapproved note or a missing file, 503 for a database problem.

Files are served only from `backend/seed_files/` and `backend/uploads/`. The `file_path` column is relative to `backend/` (for example `seed_files/linked_list_notes.pdf`). `seed_files/` holds five small sample PDFs for the demo notes.

## Upload API

`POST /notes` lets a logged-in **student** upload a PDF. The note is saved with status `pending` and stays hidden from the notes list, detail and download endpoints until an admin approves it (a later stage).

Send a `multipart/form-data` request with the header `Authorization: Bearer <token>`:

| Field | Required | Notes |
|---|---|---|
| `title` | yes | not blank, at most 200 characters |
| `description` | no | at most 5000 characters |
| `unit_id` | yes | positive integer; the unit must exist |
| `file` | yes | a PDF, not empty, at most 10 MB |

```bash
curl -X POST http://127.0.0.1:5000/notes \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=Operating Systems Unit 1" \
  -F "description=Process management notes" \
  -F "unit_id=5" \
  -F "file=@os_unit1.pdf"
```

Success is `201` with `{"message": "Note uploaded for approval", "status": "pending"}`. Errors are `{"error": "..."}`:

| Status | When |
|---|---|
| 400 | missing/blank/too long `title`, missing or invalid `unit_id`, missing/empty/non-PDF file, request not multipart |
| 401 | no token, or an invalid or expired token |
| 403 | the token belongs to an admin (only students may upload) |
| 404 | `unit_id` does not exist |
| 413 | file larger than 10 MB |
| 500 | the file could not be written to disk (no database record is created) |
| 503 | database problem (the saved file is removed again) |

How uploads are kept safe:

- The uploader is always the user in the token. An `uploader_id` sent by the client is ignored.
- A file is accepted only if its name ends in `.pdf`, its declared content type is not something else, **and** it starts with the `%PDF-` header.
- The client's file name is never used to build a path. Files are stored as `backend/uploads/<random-uuid>.pdf` and `notes.file_path` holds `uploads/<random-uuid>.pdf`. Files are created in exclusive mode, so an existing file is never overwritten.
- If the database insert fails after the file was saved, the file is deleted. If the file cannot be saved, no row is created.
- Runtime uploads go to `backend/uploads/` (ignored by git), never to `backend/seed_files/`.

## Admin API

All admin endpoints need `Authorization: Bearer <admin token>` (log in as the demo admin). Only role `admin` is allowed: a student gets `403`, a missing or invalid token `401`. The role comes from the signed token and is confirmed against the `users` table on every request; nothing the client sends in the body, query or other headers can grant it.

| Endpoint | Does |
|---|---|
| `GET /admin/notes/pending` | `{"notes": [...]}` of notes with status `pending`, oldest first (`{"notes": []}` when none) |
| `GET /admin/notes/<id>` | metadata of one note in any status |
| `GET /admin/notes/<id>/download` | the PDF of a note in any status, for review (does not count as a download) |
| `PATCH /admin/notes/<id>/approve` | `pending` to `approved`: `{"message": "Note approved", "status": "approved"}` |
| `PATCH /admin/notes/<id>/reject` | `pending` to `rejected`: `{"message": "Note rejected", "status": "rejected"}` |

Each note looks like `{"id", "title", "description", "unit_id", "uploader_id", "file_type", "status", "created_at", "download_count", "subject", "unit", "file_url"}`. No emails or password hashes are included.

Errors are `{"error": "..."}`: `400` for a bad note id or a note that is no longer pending (a processed note is never changed again), `404` for an unknown note or a missing file, `503` for a database problem (the change is rolled back).

Students keep using the Stage 5 endpoints, which only ever return `approved` notes, so a note becomes visible to students the moment it is approved and stays invisible if rejected. The admin download uses the same safe path resolution as the student download: only files inside `backend/seed_files/` and `backend/uploads/` can be served, so paths such as `../config.py` or `/etc/passwd` in a note record return `404`.

## Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The API runs at http://127.0.0.1:5000. Check it: http://127.0.0.1:5000/ping

## Start the frontend

```bash
cd frontend
npm install
npm start
```

Open http://localhost:4200 (use `localhost`, not `127.0.0.1`: the backend's CORS setting allows `http://localhost:4200`). Start the backend first.

Production build: `npm run build` (output in `frontend/dist/campusnotes-frontend/`).

### API address

The Flask URL lives in one place only:

| File | Used for |
|---|---|
| `frontend/src/environments/environment.ts` | `npm start` / development builds |
| `frontend/src/environments/environment.prod.ts` | `npm run build` (set this to the deployed backend before deploying) |

If you deploy the frontend to another origin, also add that origin to the `CORS_ALLOWED_ORIGINS` environment variable (see Environment variables).

## Using the app

**Student:** Register, then Login. Dashboard offers *Browse Notes* (Course, Semester, Subject, Unit, Notes) and *Upload Note*. The notes page has search (`?q=`) and subject/unit filters. *Open* shows the PDF in a new tab, *Download* saves it. Uploads are saved as `pending` ("Note uploaded for approval.") and appear for students only after an admin approves them.

**Admin:** Login with the demo admin. *Pending Notes* lists the queue; *Review* shows the details with an inline PDF preview; *Approve* / *Reject* update the queue immediately. Processed notes cannot be changed again.

### Frontend structure

```
frontend/src/
├── environments/        API address (dev / prod)
└── app/
    ├── core/            services, interceptors, guards, models, error messages
    │   ├── auth.service.ts        login/register, JWT + role storage, logout
    │   ├── auth.interceptor.ts    adds Authorization: Bearer <JWT>
    │   ├── error.interceptor.ts   401 -> clear session and go to Login
    │   ├── guards.ts              role-based route guards (UI only, not security)
    │   ├── academic.service.ts    /courses /semesters /subjects /units
    │   ├── notes.service.ts       /notes (list, detail, download, upload)
    │   ├── admin.service.ts       /admin/notes/... (pending, review, approve, reject)
    │   ├── file.service.ts        open/save PDFs fetched with the token
    │   └── api-error.ts           consistent human-readable error messages
    ├── shared/          state-view (loading/error/empty wrapper), unit-picker
    └── pages/           login, register, student-dashboard, browse, notes-list,
                         note-detail, upload-note, admin-dashboard, pending-notes, note-review
```

Notes on behaviour:

- The JWT and role are kept in `localStorage` (fine for this MVP, not XSS-proof). Frontend guards only hide pages; the Flask backend enforces every permission.
- PDFs are fetched with `HttpClient` (so the token is sent) and handed to the browser as a blob; plain links cannot send the `Authorization` header that admin downloads need.
- The backend counts every `GET /notes/<id>/download` as a download, so *Open* and *Download* both increase the counter.

## Known limitations

- Demo accounts and sample data in `init.sql` are for demos only. Change or delete the demo admin/student accounts before any public deployment.
- JWT and role are kept in `localStorage` (not XSS-proof).
- No password reset, email verification, or rate limiting.
- Uploaded PDFs live on local disk; the host must provide a persistent disk (`UPLOAD_DIRECTORY`).
- Backend tests need a running MySQL with `init.sql` loaded.
- Final-stage QA was static only; see `docs/FINAL_QA_REPORT.md`.

## Documentation

- `docs/FINAL_QA_REPORT.md`, `docs/DEMO_SCRIPT.md`, `docs/PRESENTATION_CONTENT.md`

## Project structure

```
CampusNotes/
├── backend/    Flask API
├── frontend/   Angular app (Stage 8: full student and admin UI)
├── docs/       Project documentation
└── README.md
```
