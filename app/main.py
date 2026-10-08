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
                     FeeRecord, Notice, Complaint, DigitalDocument, OTPChallenge, AuthorizedRegistration)
from .services.verification import create_challenge, verify_challenge

main_bp = Blueprint("main", __name__)

def _phone(v):
    import re
    return re.sub(r"\D", "", v or "")

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
        category=request.form.get("category","OTHER").strip(); subject=request.form.get("subject","").strip(); body=request.form.get("body","").strip()
        if subject and body:
            c=Complaint(student_id=current_user.id,category=category,subject=subject,body=body,department=current_user.department,hod_notified=False,principal_notified=False)
            db.session.add(c); db.session.commit()
            # Send optional real email notifications when configured. The complaint is always recorded/routed in DB.
            import smtplib
            from email.message import EmailMessage
            for addr,field in [(os.getenv("HOD_EMAIL"),"hod_notified"),(os.getenv("PRINCIPAL_EMAIL"),"principal_notified")]:
                if not addr: continue
                try:
                    host=os.getenv("SMTP_HOST"); user=os.getenv("SMTP_USERNAME"); pw=os.getenv("SMTP_PASSWORD"); sender=os.getenv("SMTP_FROM",user)
                    if not all([host,user,pw,sender]): continue
                    m=EmailMessage(); m["Subject"]=f"Smart Campus Complaint #{c.id} - {category}"; m["From"]=sender; m["To"]=addr; m.set_content(f"Complaint #{c.id}\nStudent: {current_user.full_name}\nRoll: {current_user.roll_number}\nCollege ID: {current_user.user_id}\nDepartment: {current_user.department}\nCategory: {category}\nSubject: {subject}\n\n{body}")
                    with smtplib.SMTP(host,int(os.getenv("SMTP_PORT","587")),timeout=20) as s: s.starttls(); s.login(user,pw); s.send_message(m)
                    setattr(c,field,True)
                except Exception: pass
            db.session.commit(); flash("Complaint submitted and routed to HOD + Principal.","success")
        else: flash("Category, subject and complaint are required.","error")
        return redirect(url_for("main.complaints_page"))
    rows=db.session.scalars(db.select(Complaint).where(Complaint.student_id==current_user.id).order_by(Complaint.created_at.desc())).all()
    return render_template("complaints.html",rows=rows,student=True)

@main_bp.get("/student/fees")
@login_required
def fees_page():
    if current_user.role != "STUDENT": return redirect(url_for("main.dashboard"))
    return render_template("fees.html",rows=db.session.scalars(db.select(FeeRecord).where(FeeRecord.student_id==current_user.id).order_by(FeeRecord.due_date)).all(),student=True)

@main_bp.route("/faculty/fees",methods=["GET","POST"])
@login_required
def faculty_fees():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    students=db.session.scalars(db.select(User).where(User.role=="STUDENT").order_by(User.full_name)).all()
    if request.method=="POST":
        try:
            student_id=int(request.form["student_id"]); total=float(request.form["total_amount"]); paid=float(request.form.get("paid_amount",0)); due=datetime.strptime(request.form["due_date"],"%Y-%m-%d").date() if request.form.get("due_date") else None
            last=datetime.strptime(request.form["last_paid_date"],"%Y-%m-%d").date() if request.form.get("last_paid_date") else None; count=int(request.form.get("installment_count",0) or 0); ip=int(request.form.get("installments_paid",0) or 0); ia=float(request.form.get("installment_amount",0) or 0)
            status="PAID" if paid>=total else ("PARTIAL" if paid>0 else "DUE")
            db.session.add(FeeRecord(student_id=student_id,fee_type=request.form["fee_type"].strip(),total_amount=total,paid_amount=paid,due_date=due,status=status,last_paid_date=last,installment_count=count,installments_paid=ip,installment_amount=ia)); db.session.commit(); flash("Fee record added/updated.","success")
        except Exception: flash("Enter valid fee details.","error")
        return redirect(url_for("main.faculty_fees"))
    rows=db.session.scalars(db.select(FeeRecord).order_by(FeeRecord.due_date.desc())).all(); return render_template("faculty_fees.html",students=students,rows=rows)

@main_bp.get("/profile-photo/<int:user_id>")
@login_required
def profile_photo(user_id):
    target=db.session.get(User,user_id)
    if not target or not target.photo_path: return "Photo not found",404
    if current_user.id!=target.id and current_user.role not in ("FACULTY","ADMIN"): return "Forbidden",403
    p=Path(os.getcwd())/"instance"/target.photo_path
    return send_file(p) if p.is_file() else ("Photo not found",404)

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

@main_bp.route("/change-password",methods=["GET","POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html", otp_requested=False)

    action = request.form.get("action", "request")

    if action == "request":
        entered_phone = _phone(request.form.get("registered_phone"))
        registered_phone = _phone(current_user.phone)

        if not entered_phone:
            flash("Enter your registered mobile number.", "error")
            return redirect(url_for("main.change_password"))

        if entered_phone != registered_phone:
            flash("This mobile number does not match the number registered with your account.", "error")
            return redirect(url_for("main.change_password"))

        try:
            challenge = create_challenge("CHANGE_PASSWORD", phone=registered_phone, user_id=current_user.id)
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("main.change_password"))

        flash("OTP sent to your registered mobile number.", "success")
        return render_template("change_password.html", otp_requested=True,
                               challenge_id=challenge.id, phone=registered_phone)

    try:
        challenge_id = int(request.form.get("challenge_id", 0))
    except (TypeError, ValueError):
        challenge_id = 0

    challenge = db.session.get(OTPChallenge, challenge_id)
    if (not challenge or challenge.purpose != "CHANGE_PASSWORD"
            or challenge.user_id != current_user.id
            or _phone(challenge.phone) != _phone(current_user.phone)):
        flash("Invalid or expired password-change request.", "error")
        return redirect(url_for("main.change_password"))

    ok, msg = verify_challenge(challenge, None, request.form.get("sms_otp"))
    if not ok:
        flash(msg, "error")
        return render_template("change_password.html", otp_requested=True,
                               challenge_id=challenge.id, phone=current_user.phone)

    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if len(new_password) < 8 or new_password != confirm_password:
        flash("Password must be at least 8 characters and both passwords must match.", "error")
        return render_template("change_password.html", otp_requested=True,
                               challenge_id=challenge.id, phone=current_user.phone)

    current_user.set_password(new_password)
    db.session.commit()
    flash("Password changed successfully.", "success")
    return redirect(url_for("main.dashboard"))

@main_bp.route("/faculty/attendance", methods=["GET","POST"])
@login_required
def faculty_attendance():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    if request.method=="POST":
        try:
            subject=request.form["subject"].strip(); room=request.form.get("room","").strip(); lat=float(request.form["latitude"]); lon=float(request.form["longitude"]); radius=float(request.form["radius_m"])
            if not subject or not room or radius<=0 or radius>100: raise ValueError()
            db.session.add(AttendanceSession(subject=subject, faculty_id=current_user.id, room=room, latitude=lat, longitude=lon, radius_m=radius, active=True)); db.session.commit(); flash("Attendance session created. Students can now mark attendance.","success")
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

@main_bp.route("/faculty/registration-directory", methods=["GET","POST"])
@login_required
def registration_directory():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    if request.method=="POST":
        try:
            role=request.form.get("role","STUDENT").upper().strip()
            uid=request.form.get("user_id","").strip()
            name=request.form.get("full_name","").strip()
            email=request.form.get("email","").strip().lower()
            phone=_phone(request.form.get("phone"))
            dept=request.form.get("department","").strip()
            course=request.form.get("course","").strip() or None
            roll=request.form.get("roll_number","").strip() or None
            sem=int(request.form["semester"]) if request.form.get("semester") else None
            if role not in ("STUDENT","FACULTY") or not all([uid,name,email,phone,dept]): raise ValueError()
            if len(phone)!=10 or not phone.isdigit(): raise ValueError()
            if role=="STUDENT" and (not roll or not course or not sem or uid.casefold()==roll.casefold()): raise ValueError()
            if db.session.scalar(db.select(AuthorizedRegistration).where(AuthorizedRegistration.user_id==uid)):
                flash("That ID is already in the authorized directory.","error")
            else:
                db.session.add(AuthorizedRegistration(role=role,user_id=uid,full_name=name,email=email,phone=phone,department=dept,course=course,semester=sem,roll_number=roll))
                db.session.commit(); flash("Authorized registration record added.","success")
        except Exception:
            db.session.rollback(); flash("Enter complete and valid directory details.","error")
        return redirect(url_for("main.registration_directory"))
    rows=db.session.scalars(db.select(AuthorizedRegistration).order_by(AuthorizedRegistration.role,AuthorizedRegistration.full_name)).all()
    return render_template("registration_directory.html",rows=rows)

@main_bp.route("/faculty/timetable", methods=["GET","POST"])
@login_required
def faculty_timetable():
    if current_user.role not in ("FACULTY","ADMIN"): return redirect(url_for("main.dashboard"))
    if request.method=="POST":
        try:
            d=date.fromisoformat(request.form["entry_date"])
            db.session.add(TimetableEntry(entry_type=request.form["entry_type"], title=request.form["title"].strip(), subject=(request.form.get("subject_other","").strip() if request.form.get("subject")=="Other" else request.form.get("subject","").strip()), faculty_name=current_user.full_name, room=request.form.get("room"," ").strip(), entry_date=d, start_time=request.form.get("start_time"), end_time=request.form.get("end_time"), semester=int(request.form["semester"]) if request.form.get("semester") else None, department=current_user.department))
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
