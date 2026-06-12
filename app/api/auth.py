import os
import random
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app.database.connection import get_db
from app.models.user import User
from app.core.config import settings

# OAuth2 scheme configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

router = APIRouter(tags=["auth"])

# Brevo Configuration
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = settings.BREVO_API_KEY
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

# --- Schemas ---

class UserRegister(BaseModel):
    email: EmailStr
    # Restriction: Minimum 6 characters
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")

class EmailRequest(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Helper Functions ---

def get_password_hash(password: str):
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# --- Routes ---

@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    user_exists = db.query(User).filter(User.email == user_data.email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=user_data.email, 
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@router.post("/send-otp")
def send_otp(request: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    db.commit()

    # Send via Brevo
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": user.email}],
        sender={"name": "Task Manager", "email": "your-verified-email@example.com"}, # Must be verified in Brevo
        subject="Your Login OTP",
        html_content=f"""
        <div style="font-family: sans-serif; padding: 20px; border: 1px solid #eee;">
            <h2>Secure Login</h2>
            <p>Your OTP for Project Workspace is:</p>
            <h1 style="color: #5c59c2;">{otp}</h1>
            <p>This code expires in 5 minutes.</p>
        </div>
        """
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
        return {"message": "OTP sent to email"}
    except ApiException:
        raise HTTPException(status_code=500, detail="Failed to send email")

@router.post("/login", response_model=Token)
def login(
    username: str = Form(...), 
    password: Optional[str] = Form(None), 
    otp: Optional[str] = Form(None), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email")

    # Flow 1: Login with Password
    if password:
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Flow 2: Login with OTP
    elif otp:
        if not user.otp_code or user.otp_code != otp:
            raise HTTPException(status_code=401, detail="Invalid OTP code")
        
        if datetime.utcnow() > user.otp_expiry:
            raise HTTPException(status_code=401, detail="OTP has expired")
        
        # Clear OTP after successful use
        user.otp_code = None
        user.otp_expiry = None
        db.commit()
    
    else:
        raise HTTPException(status_code=400, detail="Provide either password or OTP")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email}

# --- Security Dependency ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user