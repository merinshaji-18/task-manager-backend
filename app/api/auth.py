import os
import random
import bcrypt
import smtplib
import ssl
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.database.connection import get_db
from app.models.user import User, PendingUser
from app.models.task import Task
from app.core.config import settings

# 1. Configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
router = APIRouter(tags=["auth"])

# 2. Schemas (DEFINED FIRST TO AVOID NameError)
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserVerifyRegister(BaseModel):
    email: EmailStr
    otp: str

class EmailRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_pic: Optional[str] = None

# 3. Helper Functions
def get_password_hash(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def send_smtp_email(to_email: str, subject: str, body_html: str):

    sender_email = settings.GMAIL_EMAIL
    password = settings.GMAIL_APP_PASSWORD

    message = MIMEMultipart()
    message["From"] = f"Mission Control <{sender_email}>"
    message["To"] = to_email
    message["Subject"] = subject

    message.attach(MIMEText(body_html, "html"))

    try:
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, password)
            server.send_message(message)

        print(f"Email sent successfully to {to_email}")

    except Exception as e:
        print("EMAIL ERROR:", e)
        raise HTTPException(
            status_code=500,
            detail=f"Email delivery failed: {e}"
        )
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        user = db.query(User).filter(User.email == email).first()
        if user is None: raise HTTPException(status_code=401)
        return user
    except JWTError: raise HTTPException(status_code=401)

def get_current_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access Denied: Administrative Privileges Required")
    return current_user

# 4. Routes

# --- 2-STEP REGISTRATION ---

@router.post("/register/request")
def request_registration(data: UserRegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    otp = str(random.randint(100000, 999999))
    hashed_pwd = get_password_hash(data.password)
    
    pending = db.query(PendingUser).filter(PendingUser.email == data.email).first()
    if pending:
        pending.otp_code = otp
        pending.hashed_password = hashed_pwd
        pending.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    else:
        pending = PendingUser(email=data.email, hashed_password=hashed_pwd, otp_code=otp, otp_expiry=datetime.utcnow() + timedelta(minutes=5))
        db.add(pending)
    
    db.commit()
    send_smtp_email(data.email, "Verification Code", f"<html><body><h1>Verification Code: {otp}</h1></body></html>")
    return {"message": "OTP sent to email"}

@router.post("/register/verify")
def verify_registration(data: UserVerifyRegister, db: Session = Depends(get_db)):
    pending = db.query(PendingUser).filter(PendingUser.email == data.email).first()
    if not pending or pending.otp_code != data.otp or datetime.utcnow() > pending.otp_expiry:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    new_user = User(email=pending.email, hashed_password=pending.hashed_password)
    db.add(new_user)
    db.delete(pending)
    db.commit()
    return {"message": "Account verified and created successfully!"}

# --- PASSWORD RECOVERY ---

@router.post("/forgot-password")
def forgot_password(request: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")
    
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    send_smtp_email(user.email, "Password Reset Request", f"<html><body><h2>Reset Code: {otp}</h2></body></html>")
    return {"message": "Reset OTP sent"}

@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or user.otp_code != data.otp: raise HTTPException(status_code=401, detail="Invalid OTP")
    if datetime.utcnow() > user.otp_expiry: raise HTTPException(status_code=401, detail="Expired")
    
    user.hashed_password = get_password_hash(data.new_password)
    user.otp_code = None
    db.commit()
    return {"message": "Password updated"}

# --- AUTH & USER ---

@router.post("/login", response_model=Token)
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.email})
    return {
    "access_token": create_access_token(data={"sub": user.email}), 
    "token_type": "bearer",
    "is_admin": user.is_admin # <--- Make sure this is returned on login!
}
@router.put("/users/profile")
def update_profile(data: ProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    print(f"DEBUG: Received Profile Pic URL: {data.profile_pic[:50] if data.profile_pic else 'None'}...")
    
    if data.full_name is not None: current_user.full_name = data.full_name
    if data.bio is not None: current_user.bio = data.bio
    if data.profile_pic is not None: current_user.profile_pic = data.profile_pic
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"message": "Success"}

# Update get_me to return the picture
@router.get("/users/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "bio": current_user.bio,
        "profile_pic": current_user.profile_pic,# Added this
        "is_admin": current_user.is_admin
    }
# --- 2. GLOBAL STATS ROUTE ---
@router.get("/admin/analytics")
def get_global_stats(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    user_count = db.query(User).filter(User.is_admin.isnot(True)).count()
    task_count = db.query(Task).count()
    from app.models.task import Attachment
    file_count = db.query(Attachment).count()
    
    return {
        "total_users": user_count,
        "total_tasks": task_count,
        "total_assets": file_count,
        "server_time": datetime.utcnow()
    }

# --- 3. GLOBAL USER LIST ROUTE ---
@router.get("/admin/users/all")
def get_admin_user_list(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    users = db.query(User).filter(User.id != admin.id).all()
    return [{
        "email": u.email,
        "name": u.full_name,
        "task_count": len(u.tasks),
        "is_admin": u.is_admin
    } for u in users]