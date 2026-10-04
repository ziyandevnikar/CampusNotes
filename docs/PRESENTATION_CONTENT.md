# CampusNotes Presentation Content (10 slides)

## 1. Title
CampusNotes: Centralized Academic Notes Platform. Team / name / institution.

## 2. Problem Statement
- Notes are scattered across chat groups and drive links
- Hard to search, unorganised, no quality check

## 3. Proposed Solution
One web platform organised as Course > Semester > Subject > Unit > Notes, with admin-moderated student contributions.

## 4. Key Features (CURRENT)
- Student registration and login (JWT), role-based access
- Browse academic hierarchy from real API data
- Keyword search with subject and unit filters
- Note detail, PDF open and download
- Student PDF upload (validated, stored with unique names, status pending)
- Admin pending queue, PDF review, approve and reject
- Only approved notes are visible to students

## 5. System Workflow
Student uploads > note is pending > admin reviews > approved (visible) or rejected (hidden).

## 6. Technology Stack
Angular frontend, Flask REST API, MySQL 8 (PyMySQL), PDF files on persistent disk, JWT, Gunicorn (WSGI).

## 7. Student Workflow
Register > Login > Browse / Search > Open or download > Upload a note.

## 8. Admin Workflow
Login > Pending notes > Review with PDF preview > Approve or Reject.

## 9. Future Scope (NOT implemented)
Ratings and comments, notification of review results, richer moderation tools, cloud object storage, password reset. These are ideas only.

## 10. Conclusion
CampusNotes gives students one organised, moderated place for notes. The code is deployment ready; hosting is the remaining step.
