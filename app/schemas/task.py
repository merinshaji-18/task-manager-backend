from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "pending"
    priority: Optional[str] = "medium"
    category: Optional[str] = "General"
    due_date: Optional[datetime] = None
    
class TaskCreate(TaskBase):
    pass # This is what the user sends to create a task

#Schema for partial updates (PATCH)
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[datetime] = None

class SubTaskResponse(BaseModel):
    id: int
    title: str
    is_completed: bool
    
    class Config:
        from_attributes = True
        
class AttachmentResponse(BaseModel):
    id: int
    file_url: str
    file_name: str
    file_type: str
    class Config: from_attributes = True
    
class TaskResponse(TaskBase):
    id: int
    created_at: datetime
    owner_id: int
    sub_tasks: List[SubTaskResponse] = []
    attachments: List[AttachmentResponse] = []
    class Config:
        from_attributes = True # This tells Pydantic to read SQLAlchemy models

