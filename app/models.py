from datetime import datetime
from enum import Enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db, login_manager

class Role(str, Enum):
    STUDENT="STUDENT"; FACULTY="FACULTY"; ADMIN="ADMIN"

class User(UserMixin, db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.String(50),unique=True,nullable=False,index=True)
    password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(20),nullable=False,default=Role.STUDENT.value)
    full_name=db.Column(db.String(150),nullable=False); email=db.Column(db.String(150),unique=True); phone=db.Column(db.String(30),unique=True,index=True)
    department=db.Column(db.String(120)); course=db.Column(db.String(120)); semester=db.Column(db.Integer); roll_number=db.Column(db.String(50),unique=True)
    photo_path=db.Column(db.String(255)); face_encoding=db.Column(db.LargeBinary); created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
    def set_password(self,password): self.password_hash=generate_password_hash(password)
    def check_password(self,password): return check_password_hash(self.password_hash,password)
@login_manager.user_loader
def load_user(user_id): return db.session.get(User,int(user_id))


class AuthorizedRegistration(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    role=db.Column(db.String(20),nullable=False)
    user_id=db.Column(db.String(50),unique=True,nullable=False,index=True)
    full_name=db.Column(db.String(150),nullable=False)
    email=db.Column(db.String(150),unique=True,nullable=False,index=True)
    phone=db.Column(db.String(30),unique=True,nullable=False,index=True)
    department=db.Column(db.String(120),nullable=False)
    course=db.Column(db.String(120))
    semester=db.Column(db.Integer)
    roll_number=db.Column(db.String(50),unique=True,index=True)
    active=db.Column(db.Boolean,default=True,nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)

class OTPChallenge(db.Model):
    id=db.Column(db.Integer,primary_key=True); purpose=db.Column(db.String(40),nullable=False); user_id=db.Column(db.Integer,db.ForeignKey('user.id'))
    email=db.Column(db.String(150)); phone=db.Column(db.String(30)); email_code_hash=db.Column(db.String(255)); sms_code_hash=db.Column(db.String(255))
    payload=db.Column(db.Text); photo_temp_path=db.Column(db.String(255)); expires_at=db.Column(db.DateTime,nullable=False); attempts=db.Column(db.Integer,default=0,nullable=False)

class AttendanceSession(db.Model):
    id=db.Column(db.Integer,primary_key=True); subject=db.Column(db.String(150),nullable=False); faculty_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    room=db.Column(db.String(100)); latitude=db.Column(db.Float,nullable=False); longitude=db.Column(db.Float,nullable=False); radius_m=db.Column(db.Float,nullable=False,default=20)
    starts_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False); ends_at=db.Column(db.DateTime); active=db.Column(db.Boolean,default=True,nullable=False)
class AttendanceRecord(db.Model):
    id=db.Column(db.Integer,primary_key=True); session_id=db.Column(db.Integer,db.ForeignKey('attendance_session.id'),nullable=False); student_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    marked_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False); status=db.Column(db.String(30),default='PRESENT',nullable=False); distance_m=db.Column(db.Float); gps_accuracy_m=db.Column(db.Float); verification_method=db.Column(db.String(30),default='FACE+GEOFENCE')
class GeofenceAttempt(db.Model):
    id=db.Column(db.Integer,primary_key=True); session_id=db.Column(db.Integer,db.ForeignKey('attendance_session.id'),nullable=False); student_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    attempted_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False); latitude=db.Column(db.Float); longitude=db.Column(db.Float); distance_m=db.Column(db.Float); gps_accuracy_m=db.Column(db.Float); reason=db.Column(db.String(255),nullable=False); notified=db.Column(db.Boolean,default=False,nullable=False)
class TimetableEntry(db.Model):
    id=db.Column(db.Integer,primary_key=True); entry_type=db.Column(db.String(20),nullable=False); title=db.Column(db.String(150),nullable=False); subject=db.Column(db.String(150)); faculty_name=db.Column(db.String(150)); room=db.Column(db.String(100)); entry_date=db.Column(db.Date,nullable=False); start_time=db.Column(db.String(10)); end_time=db.Column(db.String(10)); semester=db.Column(db.Integer); department=db.Column(db.String(120))
class FeeRecord(db.Model):
    id=db.Column(db.Integer,primary_key=True); student_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); fee_type=db.Column(db.String(100),nullable=False); total_amount=db.Column(db.Float,nullable=False); paid_amount=db.Column(db.Float,default=0,nullable=False); due_date=db.Column(db.Date); status=db.Column(db.String(30),default='DUE',nullable=False); last_paid_date=db.Column(db.Date); installment_count=db.Column(db.Integer,default=0,nullable=False); installments_paid=db.Column(db.Integer,default=0,nullable=False); installment_amount=db.Column(db.Float,default=0,nullable=False)
    @property
    def due_amount(self): return max(0,self.total_amount-self.paid_amount)
class Notice(db.Model):
    id=db.Column(db.Integer,primary_key=True); title=db.Column(db.String(200),nullable=False); body=db.Column(db.Text,nullable=False); notice_type=db.Column(db.String(50),default='GENERAL'); created_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
class Complaint(db.Model):
    id=db.Column(db.Integer,primary_key=True); student_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); category=db.Column(db.String(100),nullable=False,default='OTHER'); subject=db.Column(db.String(200),nullable=False); body=db.Column(db.Text,nullable=False); department=db.Column(db.String(120)); routed_to=db.Column(db.String(100),default='HOD + PRINCIPAL'); hod_notified=db.Column(db.Boolean,default=False); principal_notified=db.Column(db.Boolean,default=False); status=db.Column(db.String(30),default='OPEN',nullable=False); created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False); resolved_at=db.Column(db.DateTime)
class DigitalDocument(db.Model):
    id=db.Column(db.Integer,primary_key=True); student_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); document_type=db.Column(db.String(100),nullable=False); title=db.Column(db.String(200),nullable=False); storage_key=db.Column(db.String(255),nullable=False); uploaded_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
class AuditLog(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id')); action=db.Column(db.String(100),nullable=False); entity_type=db.Column(db.String(100)); entity_id=db.Column(db.Integer); ip_address=db.Column(db.String(45)); created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
