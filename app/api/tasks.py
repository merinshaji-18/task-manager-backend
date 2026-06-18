from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.connection import get_db
from app.models.task import Task,Attachment
from app.models.user import User # Import User model
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.api.auth import get_current_user # Import the security dependency
from pydantic import BaseModel

router = APIRouter(prefix="/tasks", tags=["tasks"])

class AttachmentCreate(BaseModel):
    file_url: str
    file_name: str
    file_type: str

class VaultResponse(BaseModel):
    id: int
    file_name: str
    file_url: str
    client: str
    task_title: str

# 1. CREATE Task (POST /tasks) - Now attaches owner_id
@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Create the task with all fields from the schema
    new_task = Task(
        **task.model_dump(), 
        owner_id=current_user.id
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

# 2. GET ALL Tasks (GET /tasks) - Filters by current_user
@router.get("/", response_model=List[TaskResponse])
def get_tasks(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Only return tasks belonging to this user
    return db.query(Task).filter(Task.owner_id == current_user.id).all()

# 3. GET Single Task (GET /tasks/{id})
@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or unauthorized")
    return task

# 4. UPDATE Task (PUT /tasks/{id})
@router.put("/{task_id}", response_model=TaskResponse)
def update_task_full(task_id: int, updated_data: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update all fields dynamically
    for key, value in updated_data.model_dump().items():
        setattr(task, key, value)
    
    db.commit()
    db.refresh(task)
    return task

# 5. DELETE Task (DELETE /tasks/{id})
@router.delete("/{task_id}")
def delete_task(
    task_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or unauthorized")
    
    db.delete(task)
    db.commit()
    return {"message": f"Task {task_id} deleted successfully"}

# 6. PARTIAL UPDATE (PATCH /tasks/{id})
@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: int, 
    task_update: TaskUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    db_task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found or unauthorized")

    update_data = task_update.model_dump(exclude_unset=True) 
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task

# --- ATTACHMENT & VAULT ROUTES ---
@router.post("/{task_id}/attachments")
def add_attachment(
    task_id: int, 
    data: AttachmentCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Verify task belongs to user
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_file = Attachment(
        task_id=task_id,
        file_url=data.file_url,
        file_name=data.file_name,
        file_type=data.file_type
    )
    db.add(new_file)
    db.commit()
    return {"message": "File attached"}

# --- 3. Get All Files for Vault ---
@router.get("/vault/all")
def get_vault(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Join tasks and attachments to see which Client (category) they belong to
    files = db.query(Attachment).join(Task).filter(Task.owner_id == current_user.id).all()
    return [
        {
            "id": f.id,
            "file_name": f.file_name,
            "file_url": f.file_url,
            "client": f.task.category, # Group by client/category
            "task_title": f.task.title
        } for f in files
    ]