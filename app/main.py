from fastapi import FastAPI
from app.database.connection import engine, Base
from app.models import task
from app.api import tasks # Import your new router

# Create the database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

# Include the tasks router
app.include_router(tasks.router)

@app.get("/")
def home():
    return {"message": "Welcome to the Task Manager API"}