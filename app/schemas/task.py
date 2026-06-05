from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "pending"

class TaskCreate(TaskBase):
    pass # This is what the user sends to create a task

#Schema for partial updates (PATCH)
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class TaskResponse(TaskBase):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True # This tells Pydantic to read SQLAlchemy models