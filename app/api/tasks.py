from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.connection import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
router = APIRouter(prefix="/tasks", tags=["tasks"])

# 1. CREATE Task (POST /tasks)
@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    new_task = Task(title=task.title, description=task.description)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

# 2. GET ALL Tasks (GET /tasks)
@router.get("/", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(Task).all()

# 3. GET Single Task (GET /tasks/{id})
@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# 4. UPDATE Task (PUT /tasks/{id})
@router.put("/{task_id}", response_model=TaskResponse)
def update_task_full(task_id: int, updated_data: TaskCreate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.title = updated_data.title
    task.description = updated_data.description
    task.status = updated_data.status
    
    db.commit()
    db.refresh(task)
    return task

# 5. DELETE Task (DELETE /tasks/{id})
@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    return {"message": f"Task {task_id} deleted successfully"}

# 6. PARTIAL UPDATE (PATCH /tasks/{id})
@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # This logic only updates fields that are actually sent in the request
    update_data = task_update.model_dump(exclude_unset=True) 
    
    for key, value in update_data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task