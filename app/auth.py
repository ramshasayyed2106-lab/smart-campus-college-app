from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from .extensions import db
from .models import User, Role

auth_bp = Blueprint("auth", __name__)

@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("login.html")

@auth_bp.post("/login")
def login_post():
    role = request.form.get("role", "").upper().strip()
    login_id = request.form.get("login_id", "").strip()
    password = request.form.get("password", "")
    if role not in {Role.STUDENT.value, Role.FACULTY.value} or not login_id or not password:
        flash("Select Student/Faculty and enter your ID and password.", "error")
        return redirect(url_for("auth.login"))
    user = db.session.scalar(db.select(User).where(User.user_id == login_id, User.role == role))
    if not user or not user.check_password(password):
        flash("Invalid ID or password. Register first if you do not have an account.", "error")
        return redirect(url_for("auth.login"))
    login_user(user)
    return redirect(url_for("main.dashboard"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "GET":
        role = request.args.get("role", "").upper()
        if role not in {Role.STUDENT.value, Role.FACULTY.value}:
            role = ""
        return render_template("register.html", selected_role=role)

    role = request.form.get("role", "").upper().strip()
    full_name = request.form.get("full_name", "").strip()
    login_id = request.form.get("login_id", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    course = request.form.get("course", "").strip()
    semester_raw = request.form.get("semester", "").strip()
    roll_number = request.form.get("roll_number", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if role not in {Role.STUDENT.value, Role.FACULTY.value}:
        flash("Please choose Student or Faculty first.", "error")
        return redirect(url_for("main.index"))

    required = [full_name, login_id, email, phone, department, password, confirm_password]
    if role == Role.STUDENT.value:
        required += [course, semester_raw, roll_number]
    if not all(required):
        flash("All registration fields are compulsory.", "error")
        return redirect(url_for("auth.register", role=role))
    if len(password) < 6:
        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for("auth.register", role=role))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.register", role=role))
    if db.session.scalar(db.select(User).where(User.user_id == login_id)):
        flash("This ID is already registered. Use a different ID.", "error")
        return redirect(url_for("auth.register", role=role))
    if db.session.scalar(db.select(User).where(User.email == email)):
        flash("This email is already registered.", "error")
        return redirect(url_for("auth.register", role=role))
    if role == Role.STUDENT.value and db.session.scalar(db.select(User).where(User.roll_number == roll_number)):
        flash("This roll number is already registered.", "error")
        return redirect(url_for("auth.register", role=role))
    try:
        semester = int(semester_raw) if semester_raw else None
    except ValueError:
        flash("Semester must be a number.", "error")
        return redirect(url_for("auth.register", role=role))
    user = User(user_id=login_id, role=role, full_name=full_name, email=email, phone=phone,
                department=department, course=course if role == "STUDENT" else None,
                semester=semester if role == "STUDENT" else None,
                roll_number=roll_number if role == "STUDENT" else None)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("Registration successful. You can now log in.", "success")
    return redirect(url_for("auth.login"))

@auth_bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))
