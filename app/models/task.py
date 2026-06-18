from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(String, default="pending")
    priority = Column(String, default="medium") # low, medium, high, urgent
    category = Column(String, default="General") # Use this for Client Names or Projects
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))# Link to User
    
    owner = relationship("User", back_populates="tasks") 
    attachments = relationship("Attachment", back_populates="task", cascade="all, delete-orphan")

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    file_url = Column(Text, nullable=False) # Cloudinary Link
    file_name = Column(String, nullable=False) # e.g. "Logo_Final.pdf"
    file_type = Column(String) # e.g. "image/png" or "application/pdf"
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="attachments")