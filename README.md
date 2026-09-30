# Smart Campus — College Attendance & Student ERP

A production-oriented starting point for a college web/PWA application built with:

- Python 3.12
- Flask
- PostgreSQL
- Flask-SQLAlchemy
- Flask-Login
- Flask-Migrate
- Werkzeug password hashing
- OpenCV + `face_recognition` for face verification
- Server-side geofencing with the Haversine formula
- Role-based access: STUDENT, FACULTY, ADMIN
- Responsive HTML/CSS/JavaScript frontend
- PWA manifest/service worker

## Important realism notes

1. GPS is not accurate to 1 cm on normal phones. The app therefore treats the configured radius as a boundary and also considers the device's reported GPS accuracy. A student outside the allowed area is rejected and a faculty alert is created.
2. Browser geolocation can be spoofed. For a real college deployment, use an Android/iOS app with platform location services and device-attestation controls rather than relying only on browser GPS.
3. Face recognition is implemented as a verification layer, not as the sole security mechanism. A production deployment should add liveness/anti-spoofing and audit logging.
4. The app is designed for a real database. It does not hard-code student accounts or fake attendance records.

## Modules included

Student:
- Login/logout
- Dashboard
- Monthly + semester attendance
- Face registration
- Geo-fenced attendance marking
- Daily and exam timetable
- Fees / due fees / exam fees
- Digital ID card
- Notices and updates
- Complaint box
- Digital documents
- Profile
- Change password
- AI chatbot API placeholder
- Rate/share app actions

Faculty:
- Dashboard
- Create attendance sessions
- Configure allowed location/radius
- Review attendance
- View outside-geofence attempts
- Add/update timetable
- Add notices
- Manage fees
- Review complaints
- Add documents

Admin:
- Same management APIs plus user-management foundation

## Setup

### 1. Create environment

Python 3.12 is recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

`face_recognition` depends on dlib. On Windows, installation can require a compatible C++ build environment. For a college production deployment, pin a tested Python version and build environment rather than blindly upgrading Python.

### 3. PostgreSQL

Create a database, for example:

```sql
CREATE DATABASE smart_campus;
```

Set:

```text
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/smart_campus
SECRET_KEY=replace-with-a-long-random-secret
```

### 4. Initialize database

```bash
flask --app app:create_app db upgrade
```

### 5. Run

```bash
flask --app app:create_app run --debug
```

Open the displayed local URL.

## Project structure

```text
smart_campus_app/
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py
│   ├── auth.py
│   ├── main.py
│   ├── api.py
│   ├── services/
│   │   ├── geofence.py
│   │   └── face_service.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   └── dashboard.html
│   └── static/
│       ├── app.css
│       └── app.js
├── migrations/
├── .env.example
├── requirements.txt
└── run.py
```

## What should be added before actual college deployment

- PostgreSQL backup and recovery
- HTTPS
- Rate limiting
- CSRF protection on all state-changing browser forms
- Strong session/cookie settings
- Centralized audit logs
- Face liveness / anti-spoofing
- Android/iOS native geolocation if GPS enforcement is important
- College ERP/SIS integration
- Payment gateway or official fee-system integration
- Document encryption/object storage
- Data-retention and consent policy
- Principal/HOD escalation workflow
- Push notifications
- Real AI provider integration
- Automated tests and security testing
- Production WSGI server such as Gunicorn/waitress behind a reverse proxy

## One-person / one-student-account control

The application uses a 1:N face-uniqueness check during face registration:

- Each student account can have only one registered face.
- A new face is compared against all already-registered student faces.
- If the face is already associated with another account, registration is rejected.
- The institutional student ID remains the primary account identifier.
- Face verification is used as an additional identity check for attendance.

This is not a mathematical guarantee that one human can never have two accounts. Face recognition has false-match and false-non-match limitations. For actual college deployment, combine:

1. Unique college-issued student ID.
2. Verified student records from the college ERP/SIS.
3. Database uniqueness constraints on institutional IDs.
4. 1:N face-uniqueness screening.
5. Face verification for attendance.
6. Liveness/anti-spoofing.
7. Administrator-controlled recovery and re-registration with an audit trail.

If you also want to prevent account sharing, password-only login is insufficient. Require an additional identity factor, such as face verification or an institutional OTP, for sensitive actions.


## Digital Documents update
Students can upload PDF/JPG/PNG/DOC/DOCX files using the original filename. Students can view/download or delete their own uploads. Faculty and Admin can view/download student-uploaded documents.
