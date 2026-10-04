# CampusNotes Final QA Report (Stage 10)

**Classification: B. DEPLOYMENT READY - NOT LIVE**

The QA environment had no network access, no MySQL server, and could not install PyMySQL, Flask-CORS, Gunicorn, or npm packages. Anything needing those was **not run** and is marked NOT VERIFIED. Nothing here claims a passing test that was not executed.

| Area | Result |
|---|---|
| Project audit (Angular > Flask > MySQL > PDF storage, Stages 1-9 present) | Verified by inspection: all backend routes/tests and all frontend pages present |
| Backend tests | NOT RUN (needs MySQL + dependencies). Python syntax check of all backend files passed |
| Angular `npm install` / `npm run build` | NOT RUN (npm registry blocked, 403) |
| Student / admin workflow QA, responsive QA | NOT VERIFIED (needs running stack and browser) |
| Security (code review) | JWT with required exp/sub/role, role re-checked per request, uuid upload names, `%PDF-` check, path resolution restricted to seed/upload dirs, JSON errors without traces. No secrets found in source. Runtime behaviour NOT RUN |
| Persistence | NOT VERIFIED. Depends on host disk; documented in README |
| Production configuration | Verified in code: debug off by default, secrets and DB creds from env, CORS fails closed in production, `.env` and uploads git-ignored, `wsgi.py`, `gunicorn.conf.py`, Procfile, `/ping` |
| Deployment / live smoke test | NOT PERFORMED. No host or credentials available. No URL exists |

## Changes made
- Added `backend/gunicorn.conf.py` and `backend/Procfile`.
- README: corrected stale CORS note and Gunicorn command, added known limitations.
- `.gitignore`: ignore `.env.*` (except example), logs, zips.
- Added demo script and presentation content.

## Remaining issues
1. Demo accounts/data in `init.sql` must be replaced before public use.
2. `frontend/src/environments/environment.prod.ts` still has the placeholder API URL.

## Manual steps to go live
1. Run `cd backend && pip install -r requirements.txt && python -m unittest` against a MySQL with `init.sql` loaded; fix any failures.
2. `cd frontend && npm install && npm run build`.
3. Provision HTTPS hosting, MySQL 8, and a persistent disk; set env vars from `backend/.env.example` (strong `JWT_SECRET`, `CORS_ALLOWED_ORIGINS`, `UPLOAD_DIRECTORY` on the disk).
4. Set the real API URL in `environment.prod.ts`, rebuild, deploy `dist/campusnotes-frontend/`.
5. Start with `gunicorn -c gunicorn.conf.py wsgi:app`; check `GET /ping`.
6. Run the smoke test in the README, then restart the backend and confirm users, notes and PDFs remain.
