# CampusNotes

**Centralized Academic Notes Platform**

## What CampusNotes does

Students today find study material scattered across WhatsApp groups, Telegram groups, Drive links and personal chats. CampusNotes puts it in one place, organised the way a college is organised:

Course → Semester → Subject → Unit → Notes

Students can browse, search, preview and download notes, and contribute their own. Uploaded notes are reviewed by an admin before they become visible to other students.

> Current status: **Stage 3 (authentication)**. Flask API with `GET /ping`, `POST /register` and `POST /login` (JWT), the MySQL schema with seed data, and a basic Angular page. Browsing, search, upload, admin and the Angular login page come in later stages.

## Technology

| Layer    | Technology              |
|----------|-------------------------|
| Frontend | Angular                 |
| Backend  | Python Flask, Flask-CORS|
| Database | MySQL 8 via PyMySQL (no ORM) |

## Prerequisites

- Python 3.10+
- Node.js 18.19+ (or 20.11+ / 22+) and npm

## Set up the database

Requires a running MySQL 8 server.

```bash
cd backend
mysql -u root -p < init.sql
```

This creates the `campusnotes` database, the six tables and the seed data. **Re-running it drops the tables and resets the data.**

Demo credentials (local demo only):

| Role    | Email                      | Password     |
|---------|----------------------------|--------------|
| Admin   | admin@campusnotes.demo     | Admin@123    |
| Student | student@campusnotes.demo   | Student@123  |

Set the connection variables before starting Flask or running the test (see `backend/.env.example`):

| Variable      | Default       | Notes                    |
|---------------|---------------|--------------------------|
| DB_HOST       | localhost     |                          |
| DB_PORT       | 3306          |                          |
| DB_USER       | root          |                          |
| DB_PASSWORD   | (empty)       | set this to your password|
| DB_NAME       | campusnotes   |                          |
| JWT_SECRET    | none (required) | long random string; login fails without it |
| JWT_EXPIRY_HOURS | 24         | optional token lifetime  |

```bash
export DB_PASSWORD="your-mysql-password"     # Windows PowerShell: $env:DB_PASSWORD = "..."
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
cd backend
python test_db.py     # database test
python test_auth.py   # authentication tests
```

## Authentication API

- `POST /register` with `{name, email, password}` creates a student account (`201`).
- `POST /login` with `{email, password}` returns `{token, role}`.
- Send the token on protected routes (added in later stages) as `Authorization: Bearer <token>`.

Errors are returned as `{"error": "..."}` with status 400 (bad input), 401 (bad login or token) or 409 (duplicate email).

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

Open http://localhost:4200. Start the backend first to see "Backend connected" on the page.

## Project structure

```
CampusNotes/
├── backend/    Flask API
├── frontend/   Angular app
├── docs/       Project documentation
└── README.md
```
