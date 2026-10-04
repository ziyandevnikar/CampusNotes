# Stage 8: frontend test plan

Manual end-to-end checklist for the Angular app against the real Flask API and MySQL.

## Setup

```bash
# terminal 1: backend (MySQL running, init.sql loaded, env vars set as in the README)
cd backend && python app.py

# terminal 2: frontend
cd frontend && npm install && npm start      # http://localhost:4200
```

Seed data: admin `admin@campusnotes.demo` / `Admin@123`, student `student@campusnotes.demo` / `Student@123`.
Seed notes: 3 approved, 1 pending (ER Model), 1 rejected (C Loops). Have a small real PDF and a non-PDF file ready.

Build checks: `cd frontend && npm run build` must finish with no errors, and `cd backend && python test_admin.py` (re-runs the Stage 3-6 suites) must pass.

## Checklist

| # | Check | Steps | Expected |
|---|---|---|---|
| 1 | Register | `/register`, new name/email, password 6+ chars | "Account created" panel with a *Go to login* button. Same email again shows "Email is already registered". Short password / bad email show inline errors. |
| 2 | Login | Log in with the new account | Succeeds, spinner text "Logging in…" while waiting. Wrong password shows "Invalid email or password." |
| 3 | Student redirect | After student login | Lands on `/dashboard`; nav shows Dashboard, Browse Notes, Upload Note, Logout. |
| 4 | Admin redirect | Log out, log in as admin | Lands on `/admin` ("CampusNotes Admin"); nav shows Dashboard, Pending Notes, Logout only. |
| 5 | Logout | Click Logout | Back on `/login`; Back button / `/dashboard` does not show student pages. |
| 6 | Courses | Student: Browse Notes | Course list from the API (BCA). |
| 7 | Semesters | Choose a course | Semester 1, Semester 2. |
| 8 | Subjects | Choose Semester 2 | Data Structures, Database Management Systems. |
| 9 | Units | Choose Data Structures | Unit 1 and Unit 2 plus a "View all notes in this subject" button. |
| 10 | Notes | Choose a unit | Only approved notes for that unit; "Showing: ..." chip with *Clear filter*. |
| 11 | Search | `/notes`, type `stack`, then `zzzz` | Results update after a short pause; no match shows "No notes found. ..."; empty box lists all approved notes. |
| 12 | Note detail | Click a note title | Title, description, subject, unit, file type PDF. Unknown id (`/notes/9999`) shows "Note not found." |
| 13 | PDF open/download | *Open* and *Download* on a note | Open shows the PDF in a new tab (allow pop-ups); Download saves `<title>.pdf`. |
| 14 | Upload | Upload Note: title, description, pick all four unit levels, PDF | Progress bar, then success. |
| 15 | Confirmation | After upload | "Note uploaded for approval." with the pending explanation. |
| 16 | Pending queue | Admin: Pending Notes | Seed ER Model note plus the new upload, oldest first, with uploader (`User #id`), subject/unit, date, status. |
| 17 | Review | Click *Review* | Details plus inline PDF preview; *Open PDF in new tab* and *Download PDF* work. |
| 18 | Approve | Approve the uploaded note, confirm | Success message; row removed from the queue without reload. |
| 19 | Reject | Reject the ER Model note, confirm | Success message; row removed. Queue now shows "No pending notes." |
| 20 | Approved visible | Student: search for the approved title | Note appears. |
| 21 | Rejected hidden | Student: search `ER Model` | Not listed; `/notes/4` shows "Note not found." |
| 22 | Student vs admin pages | As student open `/admin`, `/admin/pending` | Redirected to `/dashboard` with "Access denied." |
| 23 | Admin vs student UI | As admin open `/upload`, `/browse` | Redirected to `/admin`; no upload link anywhere. |
| 24 | Expired auth | While logged in, set `JWT_EXPIRY_HOURS` very low (or edit the stored token in DevTools) and click something | Redirected to `/login` with "Session expired. Please log in again." |
| 25 | Network/API errors | Stop Flask and reload `/browse` or `/notes` | "Unable to connect to server." with *Try again*; works after restarting Flask. Upload a `.txt` file: "Only PDF files are allowed." |
| 26 | Mobile layout | DevTools device mode (375 px) | Hamburger menu, no horizontal scroll, pending notes become stacked cards, forms and buttons are tappable. |

## Result log

| Date | Tester | Build OK | Backend tests OK | Checklist 1-26 | Notes |
|---|---|---|---|---|---|
|  |  |  |  |  |  |
