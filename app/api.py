from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func

from .extensions import db
from .models import (
    User, AttendanceSession, AttendanceRecord, GeofenceAttempt,
    TimetableEntry, FeeRecord, Notice, Complaint, DigitalDocument
)
from .services.geofence import inside_geofence
from .services.face_service import create_face_encoding, verify_face

api_bp = Blueprint("api", __name__)


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@api_bp.get("/me")
@login_required
def me():
    return jsonify({
        "id": current_user.id,
        "user_id": current_user.user_id,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department": current_user.department,
        "course": current_user.course,
        "semester": current_user.semester,
        "roll_number": current_user.roll_number,
    })


@api_bp.post("/student/face/register")
@login_required
@role_required("STUDENT")
def register_face():
    payload = request.get_json(silent=True) or {}
    image = payload.get("image")

    if not image:
        return jsonify({"error": "Face image is required."}), 400

    if current_user.face_encoding:
        return jsonify({
            "error": "A face is already registered for this account. "
                     "Contact the college administrator if re-registration is required."
        }), 409

    # 1:N check: compare this face with every registered student's face.
    from .services.face_service import is_face_unique

    registered_faces = db.session.scalars(
        db.select(User.face_encoding).where(
            User.face_encoding.is_not(None),
            User.id != current_user.id
        )
    ).all()

    try:
        if not is_face_unique(image, registered_faces):
            return jsonify({
                "error": "This face is already registered to another student account."
            }), 409

        current_user.face_encoding = create_face_encoding(image)
        db.session.commit()

        return jsonify({
            "message": "Face registered successfully and linked to this account."
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.post("/faculty/attendance-sessions")
@login_required
@role_required("FACULTY", "ADMIN")
def create_session():
    payload = request.get_json(silent=True) or {}

    required = ["subject", "latitude", "longitude", "radius_m"]
    missing = [x for x in required if x not in payload]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    radius = float(payload["radius_m"])
    if radius <= 0 or radius > 10000:
        return jsonify({"error": "Radius must be between 1 m and 10,000 m."}), 400

    session = AttendanceSession(
        subject=payload["subject"],
        faculty_id=current_user.id,
        latitude=float(payload["latitude"]),
        longitude=float(payload["longitude"]),
        radius_m=radius,
        starts_at=datetime.utcnow(),
        active=True,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({"id": session.id, "message": "Attendance session created."})


@api_bp.post("/student/attendance/mark")
@login_required
@role_required("STUDENT")
def mark_attendance():
    payload = request.get_json(silent=True) or {}

    session_id = payload.get("session_id")
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    accuracy = payload.get("accuracy")
    face_image = payload.get("face_image")

    if None in (session_id, lat, lon) or not face_image:
        return jsonify({"error": "Session, location and face image are required."}), 400

    session = db.session.get(AttendanceSession, int(session_id))
    if not session or not session.active:
        return jsonify({"error": "Attendance session is not active."}), 400

    existing = db.session.scalar(
        db.select(AttendanceRecord).where(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_id == current_user.id
        )
    )
    if existing:
        return jsonify({"error": "Attendance already marked."}), 409

    try:
        if accuracy is not None and float(accuracy) > max(50.0, session.radius_m * 2):
            attempt=GeofenceAttempt(session_id=session.id,student_id=current_user.id,latitude=float(lat),longitude=float(lon),distance_m=None,gps_accuracy_m=float(accuracy),reason="GPS_ACCURACY_TOO_LOW",notified=True)
            db.session.add(attempt); db.session.commit()
            return jsonify({"error":"Your GPS accuracy is too low. Move to the classroom and try again.","faculty_notified":True}),403
        ok, distance = inside_geofence(
            float(lat), float(lon),
            session.latitude, session.longitude,
            session.radius_m
        )
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid location data."}), 400

    if not ok:
        attempt = GeofenceAttempt(
            session_id=session.id,
            student_id=current_user.id,
            latitude=float(lat),
            longitude=float(lon),
            distance_m=distance,
            gps_accuracy_m=float(accuracy) if accuracy is not None else None,
            reason="ATTEMPTED_OUTSIDE_ALLOWED_GEOFENCE",
            notified=True
        )
        db.session.add(attempt)
        db.session.commit()

        # In production, this should trigger a push/email/in-app faculty notification.
        return jsonify({
            "error": "You are outside the attendance area.",
            "distance_m": round(distance, 2),
            "faculty_notified": True
        }), 403

    if not current_user.face_encoding:
        return jsonify({"error": "Face is not registered. Register your face first."}), 400

    try:
        verified = verify_face(face_image, current_user.face_encoding)
    except Exception:
        verified = False

    if not verified:
        return jsonify({"error": "Face verification failed."}), 403

    record = AttendanceRecord(
        session_id=session.id,
        student_id=current_user.id,
        distance_m=distance,
        gps_accuracy_m=float(accuracy) if accuracy is not None else None,
        status="PRESENT",
        verification_method="FACE+GEOFENCE"
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({
        "message": "Attendance marked successfully.",
        "distance_m": round(distance, 2),
        "marked_at": record.marked_at.isoformat()
    })


@api_bp.get("/student/attendance")
@login_required
@role_required("STUDENT")
def student_attendance():
    rows = db.session.execute(
        db.select(
            AttendanceRecord.marked_at,
            AttendanceRecord.status,
            AttendanceSession.subject
        )
        .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
        .where(AttendanceRecord.student_id == current_user.id)
        .order_by(AttendanceRecord.marked_at.desc())
    ).all()

    return jsonify([
        {
            "date": marked_at.date().isoformat(),
            "subject": subject,
            "status": status
        }
        for marked_at, status, subject in rows
    ])


@api_bp.get("/student/attendance/summary")
@login_required
@role_required("STUDENT")
def attendance_summary():
    total = db.session.scalar(
        db.select(func.count(AttendanceRecord.id))
        .where(AttendanceRecord.student_id == current_user.id)
    ) or 0

    present = db.session.scalar(
        db.select(func.count(AttendanceRecord.id))
        .where(
            AttendanceRecord.student_id == current_user.id,
            AttendanceRecord.status == "PRESENT"
        )
    ) or 0

    percentage = round((present / total) * 100, 2) if total else 0
    return jsonify({
        "present": present,
        "total_recorded_sessions": total,
        "percentage": percentage
    })


@api_bp.get("/student/fees")
@login_required
@role_required("STUDENT")
def student_fees():
    records = db.session.scalars(
        db.select(FeeRecord)
        .where(FeeRecord.student_id == current_user.id)
        .order_by(FeeRecord.due_date)
    ).all()

    return jsonify([
        {
            "type": r.fee_type,
            "total": r.total_amount,
            "paid": r.paid_amount,
            "due": r.due_amount,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "status": r.status
        }
        for r in records
    ])


@api_bp.get("/notices")
@login_required
def notices():
    rows = db.session.scalars(
        db.select(Notice).order_by(Notice.created_at.desc())
    ).all()

    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "type": n.notice_type,
            "created_at": n.created_at.isoformat()
        }
        for n in rows
    ])


@api_bp.post("/student/complaints")
@login_required
@role_required("STUDENT")
def complaint():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject", "").strip()
    body = payload.get("body", "").strip()

    if not subject or not body:
        return jsonify({"error": "Subject and complaint are required."}), 400

    c = Complaint(
        student_id=current_user.id,
        subject=subject,
        body=body
    )
    db.session.add(c)
    db.session.commit()

    # Production: route notification to HOD + Principal based on department rules.
    return jsonify({"message": "Complaint submitted to the college complaint workflow."})


@api_bp.get("/student/timetable")
@login_required
@role_required("STUDENT")
def timetable():
    rows = db.session.scalars(
        db.select(TimetableEntry)
        .where(
            (TimetableEntry.department == current_user.department) |
            (TimetableEntry.department.is_(None)),
            (TimetableEntry.semester == current_user.semester) |
            (TimetableEntry.semester.is_(None))
        )
        .order_by(TimetableEntry.entry_date, TimetableEntry.start_time)
    ).all()

    return jsonify([
        {
            "type": r.entry_type,
            "title": r.title,
            "subject": r.subject,
            "faculty": r.faculty_name,
            "room": r.room,
            "date": r.entry_date.isoformat(),
            "start": r.start_time,
            "end": r.end_time
        }
        for r in rows
    ])
