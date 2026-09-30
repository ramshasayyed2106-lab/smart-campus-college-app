# Implementation roadmap

## Phase 1 — College core
1. Student/faculty/admin authentication.
2. PostgreSQL schema.
3. Student profile + digital ID.
4. Timetable.
5. Notices.
6. Fees.
7. Attendance records and monthly/semester reports.

## Phase 2 — Smart attendance
1. Student face registration.
2. Faculty opens a session.
3. Faculty sets latitude/longitude/radius.
4. Student sends current GPS + camera image.
5. Server checks geofence.
6. Server checks face.
7. Attendance is written to PostgreSQL.
8. Outside-area attempts are logged and shown to faculty.
9. Add push/email notification.

## Phase 3 — College workflow
1. Complaint routing to HOD and Principal.
2. Digital document storage.
3. Fee integration.
4. Exam timetable.
5. Faculty attendance correction workflow with audit trail.

## Phase 4 — Production security
1. Native mobile app for stronger location enforcement.
2. Face liveness / anti-spoofing.
3. Device/session controls.
4. HTTPS and secure cookies.
5. Rate limiting.
6. CSRF.
7. Audit logging.
8. Database backups.
9. Monitoring.
10. Penetration/security testing.

## Phase 5 — AI
The chatbot should answer from approved college data:
- timetable
- notices
- fee rules
- attendance policy
- exam schedule
- office contacts

Do not let a generic LLM invent college rules. Use retrieval from the college's own approved knowledge base and show the source notice/document where appropriate.
