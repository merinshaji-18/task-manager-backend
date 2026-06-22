from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database.connection import get_db
from app.models.task import Task, Attachment, SubTask
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.api.auth import get_current_user
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter(prefix="/tasks", tags=["tasks"])

# --- SCHEMAS ---
class AttachmentCreate(BaseModel):
    file_url: str
    file_name: str
    file_type: str

class SubTaskCreate(BaseModel):
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
        # Ensure input date is timezone aware for comparison
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        
        if due_date < now:
            raise HTTPException(
                status_code=400,
                detail="Deadline must be a future date and time"
            )

# --- ROUTES ---

@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    validate_future_date(task.due_date)
    new_task = Task(**task.model_dump(), owner_id=current_user.id)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@router.get("/", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Task).options(joinedload(Task.sub_tasks), joinedload(Task.attachments))\
             .filter(Task.owner_id == current_user.id).all()

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
    
    validate_future_date(updated_data.due_date)
    
    if task.due_date != updated_data.due_date:
        task.notification_sent = False
        
    for key, value in updated_data.model_dump().items():
        setattr(task, key, value)
    
    db.commit()
    db.refresh(task)
    return task

@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_update.due_date is not None:
        validate_future_date(task_update.due_date)

    update_data = task_update.model_dump(exclude_unset=True) 
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404)
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

# --- SUBTASKS ---
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