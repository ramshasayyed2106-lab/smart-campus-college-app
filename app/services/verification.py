import json, os, secrets, smtplib, urllib.parse, urllib.request, base64
from datetime import datetime, timedelta
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash
from .geofence import *
from ..extensions import db
from ..models import OTPChallenge

def _code(): return f"{secrets.randbelow(1000000):06d}"
def _send_email(to, code, purpose):
    host=os.getenv('SMTP_HOST'); user=os.getenv('SMTP_USERNAME'); pw=os.getenv('SMTP_PASSWORD'); sender=os.getenv('SMTP_FROM',user)
    if not all([host,user,pw,sender]): raise RuntimeError('Email OTP is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM.')
    msg=EmailMessage(); msg['Subject']=f'Smart Campus {purpose} OTP'; msg['From']=sender; msg['To']=to; msg.set_content(f'Your Smart Campus verification code is {code}. It expires in 10 minutes. Do not share this code.')
    with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=20) as s: s.starttls(); s.login(user,pw); s.send_message(msg)
def _send_sms(to, code, purpose):
    sid=os.getenv('TWILIO_ACCOUNT_SID'); token=os.getenv('TWILIO_AUTH_TOKEN'); sender=os.getenv('TWILIO_FROM_NUMBER')
    if not all([sid,token,sender]): raise RuntimeError('SMS OTP is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER.')
    data=urllib.parse.urlencode({'To':to,'From':sender,'Body':f'Smart Campus {purpose} OTP: {code}. Expires in 10 minutes.'}).encode()
    req=urllib.request.Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',data=data)
    auth=base64.b64encode(f'{sid}:{token}'.encode()).decode(); req.add_header('Authorization','Basic '+auth)
    try: urllib.request.urlopen(req,timeout=20).read()
    except Exception as e: raise RuntimeError('SMS OTP could not be sent. Check your Twilio settings.') from e
def create_challenge(purpose,email=None,phone=None,user_id=None,payload=None,photo_temp_path=None):
    email_code=_code(); sms_code=_code(); c=OTPChallenge(purpose=purpose,user_id=user_id,email=email,phone=phone,email_code_hash=generate_password_hash(email_code),sms_code_hash=generate_password_hash(sms_code),payload=json.dumps(payload or {}),photo_temp_path=photo_temp_path,expires_at=datetime.utcnow()+timedelta(minutes=10))
    db.session.add(c); db.session.commit()
    try:
        if email: _send_email(email,email_code,purpose)
        if phone: _send_sms(phone,sms_code,purpose)
    except Exception:
        db.session.delete(c); db.session.commit(); raise
    return c
def verify_challenge(c,email_code,sms_code):
    if not c or c.expires_at < datetime.utcnow(): return False,'OTP expired. Request a new OTP.'
    if c.attempts >= 5: return False,'Too many OTP attempts. Request a new OTP.'
    c.attempts += 1
    email_ok = True if not c.email_code_hash else check_password_hash(c.email_code_hash,email_code or '')
    sms_ok = True if not c.sms_code_hash else check_password_hash(c.sms_code_hash,sms_code or '')
    ok = email_ok and sms_ok
    if ok: db.session.delete(c); db.session.commit(); return True,None
    db.session.commit(); return False,'Incorrect OTP. Check the OTP sent to your registered mobile number.'
