from datetime import datetime, date
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from uuid import uuid4
from flask import send_file
from .extensions import db
from .models import (User, AttendanceSession, AttendanceRecord, GeofenceAttempt, TimetableEntry,
                     FeeRecord, Notice, Complaint, DigitalDocument)

main_bp = Blueprint("main", __name__)

@main_bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("welcome.html")

@main_bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)

@main_bp.get("/student/attendance")
@login_required
def student_attendance_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    sessions = db.session.scalars(db.select(AttendanceSession).where(AttendanceSession.active == True).order_by(AttendanceSession.starts_at.desc())).all()
    return render_template("student_attendance.html", sessions=sessions)

@main_bp.get("/student/face")
@login_required
def student_face_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    return render_template("face_register.html", user=current_user)

@main_bp.get("/student/timetable")
@login_required
def student_timetable_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    rows = db.session.scalars(db.select(TimetableEntry).where(
        (TimetableEntry.department == current_user.department) | TimetableEntry.department.is_(None),
        (TimetableEntry.semester == current_user.semester) | TimetableEntry.semester.is_(None)
    ).order_by(TimetableEntry.entry_date, TimetableEntry.start_time)).all()
    return render_template("timetable.html", rows=rows, student=True)

@main_bp.get("/notices")
@login_required
def notices_page():
    return render_template("notices.html", rows=db.session.scalars(db.select(Notice).order_by(Notice.created_at.desc())).all())

@main_bp.route("/student/complaints", methods=["GET", "POST"])
@login_required
def complaints_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        subject=request.form.get("subject","").strip(); body=request.form.get("body","").strip()
        if subject and body:
            db.session.add(Complaint(student_id=current_user.id, subject=subject, body=body)); db.session.commit(); flash("Complaint submitted to HOD + Principal workflow.","success")
        else: flash("Subject and complaint are required.","error")
        return redirect(url_for("main.complaints_page"))
    rows=db.session.scalars(db.select(Complaint).where(Complaint.student_id==current_user.id).order_by(Complaint.created_at.desc())).all()
    return render_template("complaints.html", rows=rows, student=True)

@main_bp.get("/student/fees")
@login_required
def fees_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    return render_template("fees.html", rows=db.session.scalars(db.select(FeeRecord).where(FeeRecord.student_id==current_user.id).order_by(FeeRecord.due_date)).all())

@main_bp.get("/student/id-card")
@login_required
def id_card_page():
    return render_template("id_card.html", user=current_user)

@main_bp.route("/student/documents", methods=["GET", "POST"])
@login_required
def documents_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        uploaded = request.files.get("document")
        allowed = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}
        if not uploaded or not uploaded.filename:
            flash("Please choose a document to upload.", "error")
            return redirect(url_for("main.documents_page"))
        ext = Path(uploaded.filename).suffix.lower().lstrip(".")
        if ext not in allowed:
            flash("Allowed formats: PDF, PNG, JPG, DOC and DOCX.", "error")
            return redirect(url_for("main.documents_page"))
        safe_name = secure_filename(uploaded.filename) or f"document.{ext}"
        token = uuid4().hex
        storage_dir = os.path.join(current_user.instance_path if hasattr(current_user, "instance_path") else os.path.join(os.getcwd(), "instance"), "documents", str(current_user.id))
        os.makedirs(storage_dir, exist_ok=True)
        storage_key = os.path.join("documents", str(current_user.id), f"{token}_{safe_name}")
        full_path = os.path.join(current_user.instance_path if hasattr(current_user, "instance_path") else os.path.join(os.getcwd(), "instance"), storage_key)
        uploaded.save(full_path)
        # Keep the original filename as the document name; students do not need
        # to enter a document title or type manually.
        document_name = safe_name
        db.session.add(DigitalDocument(student_id=current_user.id, document_type=ext.upper(), title=document_name, storage_key=storage_key))
        db.session.commit()
        flash("Document uploaded successfully.", "success")
        return redirect(url_for("main.documents_page"))
    rows = db.session.scalars(db.select(DigitalDocument).where(DigitalDocument.student_id == current_user.id).order_by(DigitalDocument.uploaded_at.desc())).all()
    return render_template("documents.html", rows=rows, student=True)

@main_bp.post("/student/documents/<int:document_id>/delete")
@login_required
def delete_document(document_id):
    if current_user.role != "STUDENT":
        return redirect(url_for("main.dashboard"))
    document = db.session.get(DigitalDocument, document_id)
    if not document or document.student_id != current_user.id:
        flash("Document not found.", "error")
        return redirect(url_for("main.documents_page"))

    instance_dir = os.path.join(os.getcwd(), "instance")
    path = os.path.join(instance_dir, document.storage_key)
    try:
        if os.path.isfile(path):
            os.remove(path)
        db.session.delete(document)
        db.session.commit()
        flash("Document deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not delete the document.", "error")
    return redirect(url_for("main.documents_page"))

@main_bp.get("/faculty/documents")
@login_required
def faculty_documents_page():
    if current_user.role not in ("FACULTY", "ADMIN"):
        return redirect(url_for("main.dashboard"))
    # Faculty can access documents uploaded by students.
    # Admin and Faculty both see the student document list; the download
    # route below applies the same access rule.
    stmt = db.select(DigitalDocument, User).join(User, DigitalDocument.student_id == User.id).where(User.role == "STUDENT")
    rows = db.session.execute(stmt.order_by(DigitalDocument.uploaded_at.desc())).all()
    return render_template("faculty_documents.html", rows=rows)

@main_bp.get("/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    document = db.session.get(DigitalDocument, document_id)
    if not document:
        return "Document not found", 404
    allowed = (
        current_user.role == "ADMIN"
        or (current_user.role == "STUDENT" and document.student_id == current_user.id)
        or current_user.role == "FACULTY"
    )
    if not allowed:
        return "Forbidden", 403
    instance_dir = os.path.join(os.getcwd(), "instance")
    path = os.path.join(instance_dir, document.storage_key)
    if not os.path.isfile(path):
        return "Stored document not found", 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@main_bp.get("/profile")
@login_required
def profile_page(): return render_template("profile.html", user=current_user)

@main_bp.route("/change-password", methods=["GET","POST"])
@login_required
def change_password():
    if request.method=="POST":
        old=request.form.get("old_password",""); new=request.form.get("new_password",""); confirm=request.form.get("confirm_password","")
        if not current_user.check_password(old): flash("Current password is incorrect.","error")
        elif len(new)<6: flash("New password must contain at least 6 characters.","error")
        elif new!=confirm: flash("Passwords do not match.","error")
        else: current_user.set_password(new); db.session.commit(); flash("Password changed successfully.","success"); return redirect(url_for("main.dashboard"))
    return render_template("change_password.html")

@main_bp.route("/faculty/attendance", methods=["GET","POST"])
@login_required
def faculty_attendance():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    if request.method=="POST":
        try:
            subject=request.form["subject"].strip(); lat=float(request.form["latitude"]); lon=float(request.form["longitude"]); radius=float(request.form["radius_m"])
            if not subject or radius<=0 or radius>10000: raise ValueError()
            db.session.add(AttendanceSession(subject=subject, faculty_id=current_user.id, latitude=lat, longitude=lon, radius_m=radius, active=True)); db.session.commit(); flash("Attendance session created. Students can now mark attendance.","success")
        except Exception: flash("Enter a valid subject, location and radius.","error")
        return redirect(url_for("main.faculty_attendance"))
    sessions=db.session.scalars(db.select(AttendanceSession).where(AttendanceSession.faculty_id==current_user.id).order_by(AttendanceSession.starts_at.desc())).all()
    return render_template("faculty_attendance.html", sessions=sessions)

@main_bp.post("/faculty/attendance/<int:session_id>/close")
@login_required
def close_session(session_id):
    s=db.session.get(AttendanceSession,session_id)
    if not s or s.faculty_id!=current_user.id: flash("Session not found.","error")
    else: s.active=False; s.ends_at=datetime.utcnow(); db.session.commit(); flash("Attendance session closed.","success")
    return redirect(url_for("main.faculty_attendance"))

@main_bp.route("/faculty/timetable", methods=["GET","POST"])
@login_required
def faculty_timetable():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    if request.method=="POST":
        try:
            d=date.fromisoformat(request.form["entry_date"])
            db.session.add(TimetableEntry(entry_type=request.form["entry_type"], title=request.form["title"].strip(), subject=request.form.get("subject"," ").strip(), faculty_name=current_user.full_name, room=request.form.get("room"," ").strip(), entry_date=d, start_time=request.form.get("start_time"), end_time=request.form.get("end_time"), semester=int(request.form["semester"]) if request.form.get("semester") else None, department=current_user.department))
            db.session.commit(); flash("Timetable entry added.","success")
        except Exception: flash("Please enter valid timetable details.","error")
        return redirect(url_for("main.faculty_timetable"))
    rows=db.session.scalars(db.select(TimetableEntry).where(TimetableEntry.department==current_user.department).order_by(TimetableEntry.entry_date,TimetableEntry.start_time)).all()
    return render_template("faculty_timetable.html", rows=rows)

@main_bp.route("/faculty/notices", methods=["GET","POST"])
@login_required
def faculty_notices():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    if request.method=="POST":
        title=request.form.get("title","").strip(); body=request.form.get("body","").strip(); typ=request.form.get("notice_type","GENERAL")
        if title and body: db.session.add(Notice(title=title,body=body,notice_type=typ,created_by=current_user.id)); db.session.commit(); flash("Notice published.","success")
        else: flash("Title and notice body are required.","error")
        return redirect(url_for("main.faculty_notices"))
    return render_template("faculty_notices.html", rows=db.session.scalars(db.select(Notice).order_by(Notice.created_at.desc())).all())

@main_bp.get("/faculty/complaints")
@login_required
def faculty_complaints():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    rows=db.session.scalars(db.select(Complaint).order_by(Complaint.created_at.desc())).all()
    return render_template("complaints.html", rows=rows, student=False)

@main_bp.get("/faculty/attendance/<int:session_id>/records")
@login_required
def faculty_records(session_id):
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    session=db.session.get(AttendanceSession,session_id)
    if not session: return redirect(url_for("main.faculty_attendance"))
    records=db.session.execute(db.select(AttendanceRecord,User).join(User,AttendanceRecord.student_id==User.id).where(AttendanceRecord.session_id==session_id).order_by(User.roll_number)).all()
    attempts=db.session.scalars(db.select(GeofenceAttempt).where(GeofenceAttempt.session_id==session_id).order_by(GeofenceAttempt.attempted_at.desc())).all()
    return render_template("faculty_records.html", session=session, records=records, attempts=attempts)

@main_bp.get("/chatbot")
@login_required
def chatbot(): return render_template("chatbot.html")
