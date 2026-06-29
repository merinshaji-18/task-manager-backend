from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.connection import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    otp_code = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    
    full_name = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    profile_pic = Column(Text, nullable=True) # Stores the URL or Base64 string
    is_admin = Column(Boolean, default=False)

    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime, nullable=True)
    # Link tasks to this user
    tasks = relationship("Task", back_populates="owner")

# NEW: Table to store unverified registration attempts
class PendingUser(Base):
    __tablename__ = "pending_users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    otp_code = Column(String, nullable=False)
    otp_expiry = Column(DateTime, nullable=False)