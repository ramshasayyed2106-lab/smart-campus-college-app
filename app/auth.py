import json, os, re, shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.utils import secure_filename
from .extensions import db
from .models import User, Role, OTPChallenge, AuthorizedRegistration
from .services.verification import create_challenge, verify_challenge

auth_bp=Blueprint('auth',__name__)

DEPARTMENT_OPTIONS = [
    "Computer Science",
    "Information Technology (IT)",
    "Computer Applications (BCA / BBACA)",
    "Commerce",
    "Business Administration (BBA)",
    "Arts",
    "Science",
    "Mathematics",
    "Physics",
    "Chemistry",
    "English",
    "Economics",
    "Psychology",
    "Management Studies",
    "Library",
    "Administration",
    "Other",
]

COURSE_OPTIONS = [
    "BBA(CA) / BBACA",
    "BCA",
    "B.Sc. Computer Science",
    "B.Sc. Information Technology",
    "B.Com.",
    "BBA",
    "B.A.",
    "B.Sc.",
    "M.Sc. Computer Science",
    "M.Com.",
    "M.A.",
    "MBA",
    "MCA",
    "Other",
]

def _phone(v): return re.sub(r'\D','',v or '')
@auth_bp.get('/login')
def login():
    if current_user.is_authenticated:return redirect(url_for('main.dashboard'))
    return render_template('login.html')
@auth_bp.post('/login')
def login_post():
    role=request.form.get('role','').upper().strip(); login_id=request.form.get('login_id','').strip(); password=request.form.get('password','')
    if role not in {Role.STUDENT.value,Role.FACULTY.value} or not login_id or not password: flash('Select Student/Faculty and enter your ID and password.','error'); return redirect(url_for('auth.login'))
    user=db.session.scalar(db.select(User).where(User.user_id==login_id,User.role==role))
    if not user or not user.check_password(password): flash('Invalid ID or password.','error'); return redirect(url_for('auth.login'))
    login_user(user); return redirect(url_for('main.dashboard'))
@auth_bp.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated:return redirect(url_for('main.dashboard'))
    role=request.args.get('role','').upper() if request.method=='GET' else request.form.get('role','').upper().strip()
    if request.method=='GET':
        if role not in {Role.STUDENT.value,Role.FACULTY.value}:role=''
        return render_template('register.html',selected_role=role,departments=DEPARTMENT_OPTIONS,courses=COURSE_OPTIONS)
    full=request.form.get('full_name','').strip(); login_id=request.form.get('login_id','').strip(); email=request.form.get('email','').strip().lower(); phone=_phone(request.form.get('phone')); parent_phone=_phone(request.form.get('parent_phone')); dept=request.form.get('department','').strip(); course=request.form.get('course','').strip(); sem=request.form.get('semester','').strip(); roll=request.form.get('roll_number','').strip(); pw=request.form.get('password',''); cpw=request.form.get('confirm_password',''); photo=request.files.get('photo')
    if role not in {Role.STUDENT.value,Role.FACULTY.value}: flash('Choose Student or Faculty.','error'); return redirect(url_for('main.index'))
    if dept not in DEPARTMENT_OPTIONS:
        flash('Please select a department from the list.', 'error')
        return redirect(url_for('auth.register', role=role))
    if role == 'STUDENT' and course not in COURSE_OPTIONS:
        flash('Please select a course from the list.', 'error')
        return redirect(url_for('auth.register', role=role))
    if not all([full,login_id,email,phone,dept,pw,cpw,photo and photo.filename]) or (role=='STUDENT' and not all([course,sem,roll,parent_phone])): flash('All registration fields are compulsory, including photo.','error'); return redirect(url_for('auth.register',role=role))
    if not re.fullmatch(r'[6-9]\d{9}',phone): flash('Enter a valid Indian mobile number: 10 digits starting with 6, 7, 8 or 9.','error'); return redirect(url_for('auth.register',role=role))
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]{2,}', email): flash('Enter a valid email address, for example name@gmail.com.','error'); return redirect(url_for('auth.register',role=role))
    if role=='STUDENT' and not re.fullmatch(r'[6-9]\d{9}',parent_phone): flash('Enter the parent’s valid Indian mobile number: 10 digits starting with 6, 7, 8 or 9.','error'); return redirect(url_for('auth.register',role=role))
    if role=='STUDENT' and parent_phone==phone: flash('Parent mobile number must be different from the student mobile number.','error'); return redirect(url_for('auth.register',role=role))
    if len(pw)<8 or pw!=cpw: flash('Password must be at least 8 characters and both passwords must match.','error'); return redirect(url_for('auth.register',role=role))
    if db.session.scalar(db.select(User).where(User.user_id==login_id)): flash('This ID is already registered.','error'); return redirect(url_for('auth.register',role=role))
    if db.session.scalar(db.select(User).where(User.email==email)): flash('This email is already registered.','error'); return redirect(url_for('auth.register',role=role))
    if db.session.scalar(db.select(User).where(User.phone==phone)): flash('This mobile number is already registered.','error'); return redirect(url_for('auth.register',role=role))
    if role=='STUDENT':
        if login_id.casefold()==roll.casefold(): flash('College ID and Roll Number cannot be the same.','error'); return redirect(url_for('auth.register',role=role))
        if db.session.scalar(db.select(User).where(User.roll_number==roll)): flash('This roll number is already registered.','error'); return redirect(url_for('auth.register',role=role))
        try: semester=int(sem)
        except: flash('Semester must be a number.','error'); return redirect(url_for('auth.register',role=role))
    else: semester=None; course=None; roll=None

    # Registration validates field formats and unique identifiers. It does not claim
    # to verify ownership of the email/phone without an OTP or college directory.
    ext=Path(photo.filename).suffix.lower()
    if ext not in {'.jpg','.jpeg','.png'}: flash('Photo must be JPG, JPEG or PNG.','error'); return redirect(url_for('auth.register',role=role))
    photo_dir=Path('instance')/'profile_photos'; photo_dir.mkdir(parents=True,exist_ok=True)
    filename=f'{__import__("secrets").token_hex(16)}{ext}'
    photo_path=photo_dir/filename; photo.save(photo_path)
    user=User(user_id=login_id,role=role,full_name=full,email=email,phone=phone,parent_phone=(parent_phone if role=="STUDENT" else None),department=dept,course=course,semester=semester,roll_number=roll)
    user.set_password(pw); user.photo_path=str(Path('profile_photos')/filename)
    try:
        db.session.add(user); db.session.commit()
    except Exception:
        db.session.rollback(); photo_path.unlink(missing_ok=True)
        flash('Registration could not be completed. Check that your ID, email, mobile number and roll number are unique.','error')
        return redirect(url_for('auth.register',role=role))
    flash('Registration successful. You can now log in.','success'); return redirect(url_for('auth.login'))
@auth_bp.route('/forgot-password',methods=['GET','POST'])
def forgot_password():
    if request.method=='GET': return render_template('forgot_password.html')
    phone=_phone(request.form.get('phone')); user=db.session.scalar(db.select(User).where(User.phone==phone))
    if not user: flash('No account is registered with this mobile number.','error'); return redirect(url_for('auth.forgot_password'))
    try:c=create_challenge('PASSWORD_RESET',phone=user.phone,user_id=user.id)
    except Exception as e: flash(str(e),'error'); return redirect(url_for('auth.forgot_password'))
    return redirect(url_for('auth.reset_password',challenge_id=c.id))
@auth_bp.route('/forgot-password/reset/<int:challenge_id>',methods=['GET','POST'])
def reset_password(challenge_id):
    c=db.session.get(OTPChallenge,challenge_id)
    if not c or c.purpose!='PASSWORD_RESET': flash('Reset request is invalid or expired.','error'); return redirect(url_for('auth.forgot_password'))
    if request.method=='GET': return render_template('reset_password.html',challenge_id=challenge_id,email=c.email,phone=c.phone)
    ok,msg=verify_challenge(c,None,request.form.get('sms_otp'))
    if not ok: flash(msg,'error'); return redirect(url_for('auth.reset_password',challenge_id=challenge_id))
    pw=request.form.get('new_password',''); cpw=request.form.get('confirm_password','')
    if len(pw)<8 or pw!=cpw: flash('Password must be at least 8 characters and both passwords must match.','error'); return redirect(url_for('auth.reset_password',challenge_id=challenge_id))
    user=db.session.get(User,c.user_id); user.set_password(pw); db.session.commit(); flash('Password reset successfully.','success'); return redirect(url_for('auth.login'))
@auth_bp.post('/logout')
def logout(): logout_user(); return redirect(url_for('main.index'))
