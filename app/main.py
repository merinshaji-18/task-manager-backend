from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.connection import engine, Base
from app.api import tasks, auth
from app.models.user import User # IMPORTANT: Import User
from app.models.task import Task # IMPORTANT: Import Task 

# Create the database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

# 2. Add this middleware block BEFORE including the router
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Allows your Next.js frontend
    allow_credentials=True,
    allow_methods=["*"], # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"], # Allows all headers
)

# Include the tasks router
app.include_router(auth.router)
app.include_router(tasks.router)

@app.get("/")
def home():
    return {"message": "Welcome to the Task Manager API"}