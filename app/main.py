from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.connection import engine, Base
from app.api import tasks, auth
from app.models.user import User # IMPORTANT: Import User
from app.models.task import Task # IMPORTANT: Import Task 
from app.core.scheduler import scheduler
# Create the database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

# 2. Add this middleware block BEFORE including the router
app.add_middleware(
    CORSMiddleware,
       allow_origins=[
        "http://localhost:3000",
        "https://task-manager-frontend-lemon-phi.vercel.app" # Add your exact Vercel URL here
    ],
    allow_credentials=True,
    allow_methods=["*"], # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"], # Allows all headers
)

# Include the tasks router
app.include_router(auth.router)
app.include_router(tasks.router)

@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        scheduler.start()

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()
    
@app.get("/")
def home():
    return {"message": "Welcome to the Task Manager API"}

