# CampusNotes Demo Script (about 4 minutes)

Prep: backend and frontend running, demo data loaded, one small valid PDF ready, two browser windows (student, admin). Use the demo accounts from `init.sql`.

| Time | Scene | Say / do |
|---|---|---|
| 0:00 | 1. Problem | "Study notes live in WhatsApp groups, Drive links and chats. They are hard to find and nobody checks quality." |
| 0:20 | 2. Solution | "CampusNotes puts notes in one place, organised like a college, with admin-approved uploads." |
| 0:40 | 3. Student login | Log in as the demo student. Show the dashboard. |
| 1:00 | 4. Academic hierarchy | Browse Course, Semester, Subject, Unit. |
| 1:30 | 5. Search | Search a word (e.g. "stack"), apply subject/unit filter, show the no-result state with a nonsense word. |
| 2:00 | 6. Open / download | Open a note detail, open the PDF, download it. |
| 2:20 | 7. Upload | Upload the PDF with title, description, unit. Show "Note uploaded for approval". |
| 2:50 | 8. Admin review | In the admin window: log in, Pending Notes, Review, show PDF preview. |
| 3:20 | 9. Approve | Click Approve; it leaves the queue. |
| 3:35 | 10. Student sees it | Student window: search for the new note; it now appears and downloads. |
| 3:50 | 11. Conclusion | "One place, organised, moderated. Next: hosting with persistent storage." |

Optional: upload a second note and reject it to show it never appears for students.
Keep the focus on the working product, not the code.
