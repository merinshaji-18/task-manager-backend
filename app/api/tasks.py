import requests
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database.connection import get_db
from app.models.task import Task, Attachment, SubTask
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.api.auth import get_current_user
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from app.core.email import send_task_created_email
from app.core.google_calendar import create_calendar_event, delete_calendar_event, update_calendar_event
from app.core.config import settings

router = APIRouter(prefix="/tasks", tags=["tasks"])

# --- SCHEMAS ---
class AttachmentCreate(BaseModel):
    file_url: str
    file_name: str
    file_type: str

class SubTaskCreate(BaseModel):
    title: str

class SubTaskUpdate(BaseModel): # New for editing checkpoint text
    title: str

class SubTaskResponse(BaseModel):
    id: int
    title: str
    is_completed: bool
    class Config: from_attributes = True

# --- HELPER: VALIDATE FUTURE DATE ---
def validate_future_date(due_date: Optional[datetime]):
    if due_date:
        now = datetime.now(timezone.utc)
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        if due_date < now:
            raise HTTPException(status_code=400, detail="Deadline must be a future date and time")

# --- TASK ROUTES ---
@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # --- NEW: COLLISION CHECK ---
    if task.due_date:
        # Check for any task starting 59 mins before or after this time
        start_buffer = task.due_date - timedelta(minutes=59)
        end_buffer = task.due_date + timedelta(minutes=59)
        
        conflict = db.query(Task).filter(
            Task.owner_id == current_user.id,
            Task.due_date > start_buffer,
            Task.due_date < end_buffer
        ).first()
        
        if conflict:
            raise HTTPException(
                status_code=400, 
                detail=f"Time Slot Conflict: '{conflict.title}' is already scheduled in this window."
            )
    # --- END COLLISION CHECK ---

    new_task = Task(**task.model_dump(), owner_id=current_user.id)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    if current_user.google_access_token and new_task.due_date:
        event_id = create_calendar_event(current_user, new_task)
        if event_id:
            # SAVE THE ID TO THE DB IMMEDIATELY
            new_task.google_event_id = event_id
            db.add(new_task)
            db.commit() 
            db.refresh(new_task)
            
    return new_task

@router.get("/", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Task).options(joinedload(Task.sub_tasks), joinedload(Task.attachments))\
             .filter(Task.owner_id == current_user.id).all()
@router.get("/google/connect")
def google_connect(current_user: User = Depends(get_current_user)):
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    
    # This turns the dictionary into a URL string
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return {"url": url}

@router.post("/google/exchange-token")
def exchange_token(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    
    code = data.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code missing")
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, data=payload)
    token_data = response.json()

    if "error" in token_data:
        print("--- GOOGLE API ERROR DETAILS ---")
        print(token_data) 
        print("--------------------------------")
        raise HTTPException(status_code=400, detail=token_data.get("error_description"))
    # 2. Extract tokens
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    # 3. Update the user in the database
    user = db.query(User).filter(User.id == current_user.id).first()
    user.google_access_token = token_data.get("access_token")
    if token_data.get("refresh_token"):
        user.google_refresh_token = token_data.get("refresh_token")
    
    db.commit()
    return {"message": "Google Calendar Connected Successfully!"}

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).options(joinedload(Task.sub_tasks), joinedload(Task.attachments))\
             .filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Unauthorized or not found")
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task_full(task_id: int, updated_data: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # --- NEW: COLLISION CHECK FOR UPDATE ---
    if updated_data.due_date:
        start_buffer = updated_data.due_date - timedelta(minutes=59)
        end_buffer = updated_data.due_date + timedelta(minutes=59)
        
        # Check for conflicts, but EXCLUDE the current task itself
        conflict = db.query(Task).filter(
            Task.owner_id == current_user.id,
            Task.id != task_id, 
            Task.due_date > start_buffer,
            Task.due_date < end_buffer
        ).first()
        
        if conflict:
            raise HTTPException(
                status_code=400, 
                detail=f"Collision detected with '{conflict.title}'."
            )
    # --- END COLLISION CHECK ---
    validate_future_date(updated_data.due_date)
    for key, value in updated_data.model_dump().items():
        setattr(task, key, value)
    db.commit()
    if current_user.google_access_token:
        if task.google_event_id:
            update_calendar_event(current_user, task)
        elif task.due_date: # If it didn't have a date before but has one now
            task.google_event_id = create_calendar_event(current_user, task)
            db.commit()
            
    return task

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task: raise HTTPException(status_code=404)
    if current_user.google_access_token and task.google_event_id:
        delete_calendar_event(current_user, task)
    db.delete(task)
    db.commit()
    return {"message": "Deleted successfully"}

# --- ATTACHMENTS ---
@router.post("/{task_id}/attachments")
def add_attachment(task_id: int, data: AttachmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task: raise HTTPException(status_code=404)
    new_file = Attachment(task_id=task_id, file_url=data.file_url, file_name=data.file_name, file_type=data.file_type)
    db.add(new_file)
    db.commit()
    return {"message": "Vaulted"}

@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    file = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not file: raise HTTPException(status_code=404)
    db.delete(file)
    db.commit()
    return {"message": "Removed"}

# --- SUBTASKS (CHECKPOINTS) ---
@router.post("/{task_id}/subtasks", response_model=SubTaskResponse)
def add_subtask(task_id: int, data: SubTaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task: raise HTTPException(status_code=404)
    new_sub = SubTask(task_id=task_id, title=data.title)
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return new_sub

@router.patch("/subtasks/{subtask_id}/toggle")
def toggle_subtask(subtask_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(SubTask).filter(SubTask.id == subtask_id).first()
    if not sub: raise HTTPException(status_code=404)
    sub.is_completed = not sub.is_completed
    db.commit()
    return {"is_completed": sub.is_completed}

@router.put("/subtasks/{subtask_id}") # Update title
def update_subtask(subtask_id: int, data: SubTaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(SubTask).filter(SubTask.id == subtask_id).first()
    if not sub: raise HTTPException(status_code=404)
    sub.title = data.title
    db.commit()
    return {"message": "Updated"}

@router.delete("/subtasks/{subtask_id}") # Delete subtask
def delete_subtask(subtask_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(SubTask).filter(SubTask.id == subtask_id).first()
    if not sub: raise HTTPException(status_code=404)
    db.delete(sub)
    db.commit()
    return {"message": "Removed"}
@router.get("/notifications/upcoming")
def get_upcoming_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    next_24_hours = now + timedelta(hours=24)

    tasks = db.query(Task).filter(
        Task.owner_id == current_user.id,
        Task.status == "pending",
        Task.due_date.isnot(None),
        Task.due_date >= now,
        Task.due_date <= next_24_hours
    ).all()

    return [
        {
            "id": task.id,
            "title": task.title,
            "due_date": task.due_date,
            "priority": task.priority
        }
        for task in tasks
    ]