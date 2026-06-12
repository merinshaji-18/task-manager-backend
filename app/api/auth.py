import os
import random
import bcrypt
import smtplib
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
from app.models.user import User
from app.core.config import settings

# 1. Configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
router = APIRouter(tags=["auth"])

# 2. Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

class EmailRequest(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# 4. Routes
@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(email=user_data.email, hashed_password=get_password_hash(user_data.password))
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@router.post("/send-otp")
def send_otp(request: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    db.commit()

    # --- SMTP CONFIGURATION (THE FIX) ---
    
    smtp_server = "smtp-relay.brevo.com"
    smtp_port = 587
    smtp_username = "ae70ae001@smtp-brevo.com"
    smtp_password = settings.BREVO_API_KEY # Brevo uses the API key as SMTP password
    sender_email = "taskmanagerworkspace@gmail.com" 
    
    # Create the Email Message
    message = MIMEMultipart()
    message["From"] = f"Task Manager <{sender_email}>"
    message["To"] = user.email
    message["Subject"] = "Secure Login OTP"

    html_content = f"""
    <html>
        <body style="font-family: sans-serif; padding: 20px;">
            <h2 style="color: #5c59c2;">Workspace Authentication</h2>
            <p>Your One-Time Password is:</p>
            <h1 style="background: #f4f4f9; padding: 10px; display: inline-block; border-radius: 8px;">{otp}</h1>
            <p>This code expires in 5 minutes.</p>
        </body>
    </html>
    """
    message.attach(MIMEText(html_content, "html"))

    try:
        # Connect and Send
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() # Secure the connection
            server.login(smtp_username, smtp_password)
            server.send_message(message)
        
        return {"message": "OTP sent"}
    except Exception as e:
        print(f"SMTP Error: {str(e)}")
        print(f"DEBUG: Using Username: {smtp_username}")
        print(f"DEBUG: Key length: {len(smtp_password) if smtp_password else 0}")
        raise HTTPException(status_code=500, detail="Mail Auth Failed")

@router.post("/login", response_model=Token)
def login(
    username: str = Form(...), 
    password: Optional[str] = Form(None), 
    otp: Optional[str] = Form(None), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if password:
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect password")
    elif otp:
        if not user.otp_code or user.otp_code != otp:
            raise HTTPException(status_code=401, detail="Invalid OTP code")
        
        if datetime.utcnow() > user.otp_expiry:
            raise HTTPException(status_code=401, detail="OTP invalid or expired")
        
        user.otp_code = None
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="Provide password or OTP")
    
    return {"access_token": create_access_token({"sub": user.email}), "token_type": "bearer"}

@router.get("/users/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email}